set -o errexit

pip install -r requirements.txt

python backend/manage.py collectstatic --no-input

python backend/manage.py makemigrations

python backend/manage.py migrate

python backend/manage.py loaddata backend/api/fixtures/gemini_fixture.json


if [[ $CREATE_SUPERUSER ]]
then
    python backend/manage.py shell <<EOF
from django.contrib.auth import get_user_model

User = get_user_model()

# Check if the superuser already exists to avoid duplication
if not User.objects.filter(email='$DJANGO_SUPERUSER_EMAIL').exists():
    User.objects.create_superuser(
        email='$DJANGO_SUPERUSER_EMAIL',
        password='$DJANGO_SUPERUSER_PASSWORD',
        first_name='${DJANGO_SUPERUSER_FIRST_NAME:-Admin}',  # Default value if not set
        last_name='${DJANGO_SUPERUSER_LAST_NAME:-User}',     # Default value if not set
        role=0  # Set role to ADMIN
    )
    print("Superuser created successfully.")
else:
    print("Superuser already exists.")
EOF
fi
