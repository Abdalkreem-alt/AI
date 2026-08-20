1- One 
```
                    BUG HUNTER AGENT
                           │
                 ┌─────────▼─────────┐
                 │ Understand Target │
                 └─────────┬─────────┘
                           │
                       RECON
                           │
                    Build Asset Map
                           │
                           ▼
                  Understand Application
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
            JS            API          Browser
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                  Build Security Model
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           AuthN          AuthZ       Business Logic
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                 Generate Hypotheses
                           │
                           ▼
                    Targeted Testing
                           │
                           ▼
                     Validation
                           │
                     ┌─────┴─────┐
                     ▼           ▼
                  Invalid      Valid
                     │           │
                     │           ▼
                     │       Evidence
                     │           │
                     │           ▼
                     │       Deduplicate
                     │           │
                     │           ▼
                     └──────► Report
```


