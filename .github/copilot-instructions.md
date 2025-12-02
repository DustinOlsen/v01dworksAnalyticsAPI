# Project Instructions

- [x] Verify that the copilot-instructions.md file in the .github directory is created.
- [x] Clarify Project Requirements
- [x] Scaffold the Project
- [x] Customize the Project
- [x] Install Required Extensions
- [x] Compile the Project
- [x] Create and Run Task
- [x] Launch the Project
- [x] Ensure Documentation is Complete

## Project Overview
This is a privacy-focused visitor tracker API built with Python and FastAPI.
It uses SQLite for storage and GeoLite2 for country lookup.
IP addresses are hashed with a salt to ensure privacy.

## Execution Guidelines
- Use `uvicorn main:app --reload` to run the server.
- Ensure `GeoLite2-City.mmdb` is present in the root for country stats.
