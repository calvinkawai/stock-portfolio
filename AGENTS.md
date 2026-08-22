## Overview
This is a FastAPI-based web application designed to allow users to share their stock portfolio positions with friends. The goal is to share the *relative weight* of holdings rather than actual financial amounts, ensuring privacy while still providing a view into each other's investment strategies.

## Tech Stack
- **Backend:** FastAPI (Python)
- **Database:** SQLite
- **ORM:** SQLModel
- **Authentication:** Session-based authentication using UUID4 tokens stored in cookies.
- **External APIs:** `yfinance` (for fetching real-time/historical stock data)

## Core Features & Business Logic
- **Privacy First:** The application **must not** store or display personal financial information such as the total amount of money invested in any position.
- **Percentage-Based Tracking:** 
    - Users provide the percentage weight of each stock in their portfolio during initial setup.
    - The application tracks these percentages.
- **Position Recalculation:** 
    - Positions are recalculated at the end of each day.
    - For the current phase, this is a manual process: An admin will trigger a refresh by providing a list of unique tickers derived from the active positions of all users.
- **Sharing:** Users can share their (anonymized/percentage-based) portfolios with friends. (Note: Public/Friends permission system is still being defined).

## Data Model Highlights
- **User & Session:** `User` model with `Session` table for authentication.
- **Portfolios:** `Portfolio` belongs to a `User` and contains multiple `Holdings`.
- **Holdings:** Tracks `percentage` allocation, `buy_price`, `sell_price`, and `status` ("OPEN"/"CLOSED").
- **Ticker Management:** Handled via a `ticker` service/router to manage unique stock symbols.

## Agent Working Rules
- **Plan Before Editing:** Before modifying any file, the agent MUST first present a short written plan covering: which files will be changed, what will change in each, and the expected outcome. Edits begin only after the user has approved the plan (or has explicitly approved it inline, e.g. "just do it").
- **One Plan Per Change Set:** The plan should cover the full set of related edits, not just the first file, so the user can review the whole scope at once.
- **Stay Within the Plan:** If implementation reveals the plan needs to change, stop, present the updated plan, and get approval before continuing.
- **Reading is Free:** Reading, searching, and running non-mutating commands (tests, `ls`, `grep`) do not require a plan.
- **Edit Small** When editing files, target the smallest possible unique block of code for "oldText" (ideally 1–2 lines). Ensure you replicate indentation character-for-character. If an edit fails, immediately fall back to rewriting the file entirely using the "write" tool.


## Development Notes
- Use `SQLModel` for all database interactions.
- Ensure the admin interface for manual refreshing is secure and only accessible to authorized users.
- Optimize the `yfinance` fetching logic to handle batches of unique tickers efficiently.

## Remaining To-Do / Clarifications
- **Permissions:** Define how "friends" or "shared access" is implemented (e.g., a `SharedPortfolio` join table or a `Follow` system).
- **Admin Role:** Implement a specific role/flag for admin users to access the manual ticker refresh.
- **Admin UI:** Determine if the admin refresh is a dashboard button, a CLI command, or a specific internal endpoint.
