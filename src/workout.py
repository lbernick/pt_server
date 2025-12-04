import json

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_utils import call_ai_agent
from auth import AuthenticatedUser, get_or_create_user
from client import get_anthropic_client
from database import get_db
from models import TrainingPlanDB
from typedefs import OnboardingState, TrainingPlan, TrainingPlanResponse, Workout

router = APIRouter(prefix="/api/v1", tags=["workout"])


class WorkoutRequest(BaseModel):
    prompt: str
    difficulty: str | None = None
    duration_minutes: int | None = None


def get_workout_schema_prompt() -> str:
    """Generate schema description from Pydantic model"""
    schema = Workout.model_json_schema()
    return f"""You are a fitness expert. Generate workout plans in valid JSON format.

The JSON must match this exact schema:

{json.dumps(schema, indent=2)}

CRITICAL: Return ONLY valid JSON matching this schema. No markdown,
no explanation, no code blocks."""


@router.post("/generate-workout", response_model=Workout)
async def generate_workout(
    request: WorkoutRequest, client: Anthropic = Depends(get_anthropic_client)
):
    """Generate a workout based on user prompt and optional parameters."""
    user_prompt = f"Generate a workout based on: {request.prompt}"
    if request.difficulty:
        user_prompt += f"\nDifficulty: {request.difficulty}"
    if request.duration_minutes:
        user_prompt += f"\nTarget duration: {request.duration_minutes} minutes"

    return call_ai_agent(
        client=client,
        system_prompt=get_workout_schema_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
        response_model=Workout,
        max_tokens=4096,
        error_prefix="Workout generation",
    )


def get_training_plan_schema_prompt() -> str:
    """Generate schema description for TrainingPlan model"""
    schema = TrainingPlan.model_json_schema()
    return f"""You are a fitness expert creating personalized weekly training plans.

Generate a training plan in valid JSON format matching this exact schema:

{json.dumps(schema, indent=2)}

A Template contains:
- name: descriptive name for the workout (e.g., "Upper Body Strength",
  "Lower Body Power")
- description: brief overview of the workout's focus
- exercises: list of exercises that will be performed (e.g.,
  "Barbell Squat", "Bench Press", "Lunge"). Exercise names should
  be singular.

A Training plan contains:
- description: e.g. "3-day push-pull-legs strength training plan",
  "13-week marathon training plan"
- templates: a list of Template objects
- microcycle: a list containing the indexes of the template used on
  each day, or -1 for no workout. The microcycle will be repeated once
  complete and its length should be a multiple of 7, so that each
  template is repeated on the same day of the week. Assume the week
  starts on Monday.

Create a comprehensive weekly plan based on the user's:
- Fitness goals
- Experience level
- Available training days per week
- Available equipment
- Any injuries or limitations
- Preferences

CRITICAL: Return ONLY valid JSON matching this schema. No markdown,
no explanation, no code blocks. Assign workouts to specific days based
on the days_per_week. Leave unassigned days as null."""


def build_training_plan_prompt(state: OnboardingState) -> str:
    """Build user prompt from onboarding state.

    Args:
        state: OnboardingState with user's fitness profile

    Returns:
        Formatted prompt string for AI
    """
    prompt_parts = [
        "Generate a weekly training plan based on the following information:"
    ]

    if state.fitness_goals:
        prompt_parts.append(f"Fitness Goals: {', '.join(state.fitness_goals)}")

    if state.experience_level:
        prompt_parts.append(f"Experience Level: {state.experience_level}")

    if state.current_routine:
        prompt_parts.append(f"Current Routine: {state.current_routine}")

    if state.days_per_week:
        prompt_parts.append(f"Training Days Per Week: {state.days_per_week}")

    if state.equipment_available:
        prompt_parts.append(
            f"Available Equipment: {', '.join(state.equipment_available)}"
        )

    if state.injuries_limitations:
        prompt_parts.append(
            f"Injuries/Limitations: {', '.join(state.injuries_limitations)}"
        )

    if state.preferences:
        prompt_parts.append(f"Preferences: {state.preferences}")

    return "\n".join(prompt_parts)


def generate_plan_with_ai(client: Anthropic, state: OnboardingState) -> TrainingPlan:
    """Generate training plan using AI.

    Args:
        client: Anthropic client instance
        state: OnboardingState with user's fitness profile

    Returns:
        TrainingPlan pydantic model from AI
    """
    user_prompt = build_training_plan_prompt(state)

    return call_ai_agent(
        client=client,
        system_prompt=get_training_plan_schema_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
        response_model=TrainingPlan,
        max_tokens=4096,
        error_prefix="Training plan generation",
    )


def save_training_plan_to_db(
    db: Session, plan: TrainingPlan, user_id
) -> TrainingPlanDB:
    """Save generated training plan to database.

    Args:
        db: Database session
        plan: TrainingPlan pydantic model from AI
        user_id: UUID of the user creating the plan

    Returns:
        TrainingPlanDB instance with related templates and schedule items
    """
    from models import ScheduleItemDB, TemplateDB

    # Create the training plan
    db_plan = TrainingPlanDB(description=plan.description, user_id=user_id)
    db.add(db_plan)
    db.flush()  # Get the ID without committing

    # Create templates and map them by their index in the templates array
    template_map = {}  # Maps index -> TemplateDB
    for idx, template in enumerate(plan.templates):
        db_template = TemplateDB(
            user_id=user_id,
            name=template.name,
            description=template.description,
            exercises=template.exercises,
        )
        db.add(db_template)
        db.flush()  # Get the ID
        template_map[idx] = db_template

    # Create schedule items for each day in the microcycle
    for day_index, template_index in enumerate(plan.microcycle):
        template_id = None if template_index == -1 else template_map[template_index].id

        schedule_item = ScheduleItemDB(
            training_plan_id=db_plan.id,
            template_id=template_id,
            day_index=day_index,
        )
        db.add(schedule_item)

    db.commit()
    db.refresh(db_plan)

    return db_plan


def convert_db_to_response(db_plan: TrainingPlanDB) -> TrainingPlanResponse:
    """Convert database model to API response format.

    Args:
        db_plan: TrainingPlanDB with loaded relationships

    Returns:
        TrainingPlanResponse with microcycle array format
    """
    from typedefs import TemplateResponse

    # Build a map of template_id -> position in templates array
    # We need to deduplicate templates and assign them consistent indices
    unique_templates = {}  # template_id -> (index, TemplateDB)
    template_list = []  # Ordered list of TemplateResponse

    # First pass: collect unique templates from schedule items
    for schedule_item in db_plan.schedule_items:
        if (
            schedule_item.template_id
            and schedule_item.template_id not in unique_templates
        ):
            idx = len(unique_templates)
            unique_templates[schedule_item.template_id] = (idx, schedule_item.template)
            template_list.append(
                TemplateResponse(
                    id=schedule_item.template.id,
                    name=schedule_item.template.name,
                    description=schedule_item.template.description,
                    exercises=schedule_item.template.exercises,
                )
            )

    # Second pass: build microcycle array using template indices
    microcycle = []
    for schedule_item in db_plan.schedule_items:
        if schedule_item.template_id is None:
            microcycle.append(-1)  # Rest day
        else:
            template_idx, _ = unique_templates[schedule_item.template_id]
            microcycle.append(template_idx)

    return TrainingPlanResponse(
        id=db_plan.id,
        description=db_plan.description,
        templates=template_list,
        microcycle=microcycle,
        created_at=db_plan.created_at,
        updated_at=db_plan.updated_at,
    )


@router.post("/generate-training-plan", response_model=TrainingPlanResponse)
async def generate_training_plan(
    state: OnboardingState,
    client: Anthropic = Depends(get_anthropic_client),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_or_create_user),
):
    """Generate a weekly training plan based on onboarding information.

    This endpoint:
    1. Validates onboarding state
    2. Generates a training plan using AI
    3. Saves the plan to the database
    4. Returns the plan with database IDs
    """
    # Generate plan using AI
    plan = generate_plan_with_ai(client, state)

    # Save to database
    db_plan = save_training_plan_to_db(db, plan, user.user_id)

    # Convert to response format and return
    return convert_db_to_response(db_plan)


@router.get("/training-plan", response_model=TrainingPlanResponse)
async def get_training_plan(
    db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_or_create_user)
):
    """Get the user's current training plan.

    Returns the most recently created training plan for the authenticated user.

    Returns:
        TrainingPlanResponse with the most recent plan

    Raises:
        HTTPException: 404 if no training plan exists
    """
    # Get the most recently created training plan for this user
    db_plan = (
        db.query(TrainingPlanDB)
        .filter(TrainingPlanDB.user_id == user.user_id)
        .order_by(TrainingPlanDB.created_at.desc())
        .first()
    )

    if not db_plan:
        raise HTTPException(status_code=404, detail="No training plan found")

    # Convert to response format and return
    return convert_db_to_response(db_plan)
