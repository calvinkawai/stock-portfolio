from sqlmodel import Session, SQLModel, create_engine, select
from db.session import engine, create_db_and_tables
from models.user import User
from models.portfolio import Portfolio, Holding
from core.security import hash_password
from repositories.user_repo import get_user_by_username

def seed_data():
    # Ensure tables exist
    create_db_and_tables()

    with Session(engine) as session:
        # Check if user 'calvin' exists
        user = get_user_by_username(session, "calvin")

        if not user:
            print("Creating user 'calvin'...")
            new_user = User(
                username="calvin",
                hashed_password=hash_password("password123")
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            user = new_user
        else:
            print("User 'calvin' already exists.")

        # Check if portfolio exists for calvin
        statement = select(Portfolio).where(Portfolio.user_id == user.id)
        portfolio = session.exec(statement).first()
        print(portfolio)

        if not portfolio:
            print(f"Creating portfolio for user {user.username}...")
            new_portfolio = Portfolio(
                name="Main Portfolio",
                description="Primary investment portfolio for calvin",
                user_id=user.id
            )
            session.add(new_portfolio)
            session.commit()
            session.refresh(new_portfolio)
            portfolio = new_portfolio
        else:
            print(f"Portfolio already exists for user {user.username}.")

        # # Check if holdings exist
        statement = select(Holding).where(Holding.portfolio_id == portfolio.id)
        holdings = session.exec(statement).all()
        print(holdings)
        if not holdings:
            print("Adding mock holdings...")
            mock_holdings = [
                Holding(
                    portfolio_id=portfolio.id,
                    symbol="AAPL",
                    unit=40,
                    buy_price=150.0,
                    eod_price=180.0,
                    status="OPEN",
                    notes="Core tech holding"
                ),
                Holding(
                    portfolio_id=portfolio.id,
                    symbol="NVDA",
                    unit=40,
                    buy_price=400.0,
                    eod_price=450.0,
                    status="OPEN",
                    notes="AI growth play"
                ),
                Holding(
                    portfolio_id=portfolio.id,
                    symbol="MSFT",
                    unit=20,
                    buy_price=300.0,
                    eod_price=380.0,
                    status="OPEN",
                    notes="Cloud infrastructure"
                ),
                Holding(
                    portfolio_id=portfolio.id,
                    symbol="TSLA",
                    unit=10,
                    buy_price=200.0,
                    eod_price=170.0,
                    status="OPEN",
                    notes="EV exposure"
                ),
            ]
            for h in mock_holdings:
                session.add(h)
            session.commit()
            print("Mock holdings added successfully.")
        else:
            print(f"Portfolio already has {len(holdings)} holdings.")

if __name__ == "__main__":
    seed_data()
