A python webserver backing an AI-based [personal training/fitness app](https://github.com/lbernick/pt_app).
Backed by a Postgres database to store users, training plans, and workouts.
Wraps an LLM API with context about the user's fitness goals, current routines, limitations, and preferences.
Currently, conversations between the user and the AI are stateless, with prior messages and context passed
by the client. In the future, they'll be stored server-side, and used as context for subsequent interactions between the user and their AI personal trainer.
It's also mainly geared towards strength workouts, but I'd like for it to generically support many types of workouts/plans, especially running workouts and mobility too.

## Workflows
- *Onboarding and plan generation*: The AI asks the user about their goals, current routine, etc until it has enough information to build a training plan. It then generates some workout templates for the user to follow, and a plan for how these templates will repeat regularly.
- *Set and rep scheme generation*: The AI uses the training plan and workout history to generate suggested rep counts and weights for the current week's templated workouts.
- *Workout tracking* (In progress): The user can start a workout, tick off sets as they are completed, and finish the workout, saving it to their history.
- *Plan modification* (TODO): The user can request changes to their plan and the AI can generate updates. For example, "I'm traveling next week, can you modify next week's workouts to not use gym equipment?". The user should also be able to update templates and move workouts around on their calendar.
- *Plan extension* (TODO): Each week, the AI should add a new week onto the plan.

## Future features
- Training blocks (e.g. deload weeks)
- Rest timers
- Workout or exercise notes
- Warm-ups/cool-downs
- Settings (metric vs imperial)
- Editing templates
- Plate calculators
- Optional exercises
