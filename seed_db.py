import random
from datetime import datetime
from pathlib import Path

from faker import Faker # Import Faker
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.orm import sessionmaker

# --- Adjust these imports based on your actual project structure ---
from app.core.config import settings # Assuming settings has DATABASE_URL
from app.features.auth.models import User, Role, UserRole # Import Auth models
from app.features.suppliers.models import Supplier # Import Supplier model
from app.features.products.models import Product # Import Product model
from app.features.orders.models import ( # Import Order models
    ClientOrder,
    ClientOrderProduct,
    SupplierOrder,
    OrderStatus,
)
# --- End Imports ---

# --- Configuration ---
# Override DATABASE_URL for seeding script to use test.db
# Place test.db in the root directory relative to where you run the script
# Or provide an absolute path
DATABASE_FILE = "test.db"
TEST_DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Delete existing DB file if it exists to start fresh
db_path = Path(DATABASE_FILE)
if db_path.exists():
    db_path.unlink()
    print(f"Removed existing database: {DATABASE_FILE}")


# Use the test database URL
engine = create_engine(TEST_DATABASE_URL, echo=True, connect_args={"check_same_thread": False})

# Session factory (optional, but can be useful)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Faker instance
fake = Faker()

# --- Helper Functions ---

def create_db_and_tables():
    """Creates the database file and all tables."""
    print("Creating database and tables...")
    SQLModel.metadata.create_all(engine)
    print("Database and tables created.")

# --- Main Seeding Logic ---

def main():
    """Seeds the database with fake data."""
    create_db_and_tables()

    # Use a session context manager
    with Session(engine) as session:
        print("Seeding initial data...")

        # 1. Seed Roles
        print("Seeding Roles...")
        role_admin = Role(title="admin")
        role_customer = Role(title="customer")
        session.add(role_admin)
        session.add(role_customer)
        session.commit()
        # Refresh to get IDs assigned by the database
        session.refresh(role_admin)
        session.refresh(role_customer)
        print(f"Created Roles: {[role_admin.title, role_customer.title]}")

        # 2. Seed Users
        print("Seeding Users...")
        users = []
        admin_user = User(
            email="admin@example.com",
            full_name="Admin User",
            password="adminpassword", 
            is_active=True,
            roles=[role_admin] # Assign the admin role object
        )
        session.add(admin_user)
        users.append(admin_user)

        for _ in range(10): # Create 10 customer users
            user = User(
                email=fake.unique.email(),
                full_name=fake.name(),
                password=fake.password(),
                is_active=random.choice([True, True, False]), # Mostly active
                roles=[role_customer] # Assign the customer role object
            )
            session.add(user)
            users.append(user)

        session.commit() # Commit users and their role links
        # Refresh users to get IDs
        for user in users:
             session.refresh(user)
        print(f"Created {len(users)} Users.")
        # Keep track of customer users for orders
        customer_users = [u for u in users if u.id != admin_user.id]


        # 3. Seed Suppliers
        print("Seeding Suppliers...")
        suppliers = []
        for _ in range(5): # Create 5 suppliers
            supplier = Supplier(
                name=fake.unique.company(),
                email=fake.unique.company_email(),
                phone=fake.phone_number(),
                address=fake.street_address(),
                city=fake.city(),
                state=fake.state_abbr(),
                country=fake.country(),
                postal_code=fake.postcode(),
                is_active=True
            )
            session.add(supplier)
            suppliers.append(supplier)
        session.commit()
        # Refresh suppliers to get IDs
        for supplier in suppliers:
             session.refresh(supplier)
        print(f"Created {len(suppliers)} Suppliers.")


        # 4. Seed Products
        print("Seeding Products...")
        products = []
        for _ in range(30): # Create 30 products
            assigned_supplier = random.choice(suppliers)
            product = Product(
                name=f"{fake.word().capitalize()} {fake.word().capitalize()}",
                description=fake.sentence(nb_words=10),
                price=round(random.uniform(5.0, 200.0), 2),
                stock=random.randint(0, 100),
                supplier_id=assigned_supplier.id # Link to a supplier
            )
            session.add(product)
            products.append(product)
        session.commit()
        # Refresh products to get IDs
        for product in products:
             session.refresh(product)
        print(f"Created {len(products)} Products.")


        # 5. Seed Client Orders
        print("Seeding Client Orders...")
        client_orders_created = 0
        if customer_users and products: # Ensure we have customers and products
            for _ in range(15): # Create 15 client orders
                client = random.choice(customer_users)
                num_products_in_order = random.randint(1, 4)
                order_products_sample = random.sample(products, num_products_in_order)

                total_order_price = 0.0
                product_links_to_create = []

                # Prepare product links and calculate total price
                for prod in order_products_sample:
                     if prod.stock > 0: # Only add if in stock
                         amount = random.randint(1, min(5, prod.stock)) # Order between 1 and 5, or available stock
                         unit_price = prod.price # Price at time of order
                         total_order_price += amount * unit_price
                         product_links_to_create.append({
                             "product_id": prod.id,
                             "amount": amount,
                             "unit_price": unit_price
                         })
                         # Note: We are not decrementing stock in this seed script for simplicity

                if not product_links_to_create: # Skip if no valid products could be added
                     continue

                # Create the main order
                client_order = ClientOrder(
                    client_id=client.id,
                    total_price=round(total_order_price, 2),
                    status=random.choice(list(OrderStatus)) # Assign random status
                )
                session.add(client_order)
                session.flush() # Flush to get the client_order.id before creating links

                if client_order.id:
                     # Create the link table entries
                     for link_data in product_links_to_create:
                          order_product_link = ClientOrderProduct(
                              order_id=client_order.id,
                              product_id=link_data["product_id"],
                              amount=link_data["amount"],
                              unit_price=link_data["unit_price"]
                          )
                          session.add(order_product_link)
                     client_orders_created += 1
                else:
                     print(f"Warning: Could not get ID for client order for user {client.id}")


            session.commit() # Commit all orders and links created in this loop
            print(f"Created {client_orders_created} Client Orders.")
        else:
             print("Skipping Client Orders seeding (no customers or products found).")


        # 6. Seed Supplier Orders (Optional based on your needs)
        print("Seeding Supplier Orders...")
        if suppliers and products:
            supplier_orders_created = 0
            for _ in range(10): # Create 10 supplier orders
                supplier = random.choice(suppliers)
                product_to_order = random.choice(products)
                amount = random.randint(10, 50)
                # Fake a supplier price (e.g., 60% of client price)
                supplier_unit_price = round(product_to_order.price * random.uniform(0.5, 0.7), 2)
                total_sup_price = round(amount * supplier_unit_price, 2)

                supplier_order = SupplierOrder(
                    supplier_id=supplier.id,
                    product_id=product_to_order.id,
                    amount=amount,
                    total_price=total_sup_price,
                    status=random.choice(["placed", "received", "pending"])
                )
                session.add(supplier_order)
                supplier_orders_created += 1

            session.commit()
            print(f"Created {supplier_orders_created} Supplier Orders.")
        else:
             print("Skipping Supplier Orders seeding (no suppliers or products found).")


        print("--- Seeding complete ---")

# --- Run the main function ---
if __name__ == "__main__":
    main()