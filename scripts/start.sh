#!/bin/bash

# Blog API Setup Script
# This script sets up the entire project from scratch

set -e  # Exit on any error

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Blog API Setup Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please copy .env.example to .env and fill in the values."
    exit 1
fi

# Load and validate environment variables
echo -e "\n${YELLOW}Validating environment variables...${NC}"
source .env

REQUIRED_VARS=("BLOG_SECRET_KEY" "BLOG_DEBUG" "BLOG_ALLOWED_HOSTS" "BLOG_REDIS_URL")
MISSING_VARS=0

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}✗ $var is not set${NC}"
        MISSING_VARS=1
    else
        echo -e "${GREEN}✓ $var is set${NC}"
    fi
done

if [ $MISSING_VARS -eq 1 ]; then
    echo -e "${RED}Error: Missing required environment variables. Please check .env file.${NC}"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "\n${YELLOW}Virtual environment already exists, skipping...${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements/dev.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Run migrations
echo -e "\n${YELLOW}Running migrations...${NC}"
python manage.py migrate
echo -e "${GREEN}✓ Migrations complete${NC}"

# Collect static files
echo -e "\n${YELLOW}Collecting static files...${NC}"
python manage.py collectstatic --noinput
echo -e "${GREEN}✓ Static files collected${NC}"

# Compile translation files
echo -e "\n${YELLOW}Compiling translations...${NC}"
python manage.py compilemessages
echo -e "${GREEN}✓ Translations compiled${NC}"

# Create superuser if it doesn't exist
echo -e "\n${YELLOW}Creating superuser...${NC}"
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@example.com').exists():
    User.objects.create_superuser('admin@example.com', 'admin123', first_name='Admin', last_name='User')
    print('✓ Superuser created')
else:
    print('✓ Superuser already exists')
"

# Seed database with test data
echo -e "\n${YELLOW}Seeding database with test data...${NC}"
python manage.py shell -c "
import random
from django.contrib.auth import get_user_model
from apps.blog.models import Category, Tag, Post, Comment, PostStatus

User = get_user_model()

# Create test users
users = []
for i in range(1, 6):
    email = f'testuser{i}@example.com'
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'first_name': f'Test{i}',
            'last_name': 'User',
            'preferred_language': random.choice(['en', 'ru', 'kz']),
        }
    )
    if created:
        user.set_password('password123')
        user.save()
    users.append(user)
print('✓ Test users created')

# Create categories
# Note: field is name_kz (not name_kk) — must match the model definition
categories = []
for name_en, name_ru, name_kz in [
    ('Technology', 'Технологии', 'Технология'),
    ('Travel', 'Путешествия', 'Саяхат'),
    ('Food', 'Еда', 'Тағам'),
    ('Sports', 'Спорт', 'Спорт'),
]:
    cat, _ = Category.objects.get_or_create(
        slug=name_en.lower(),
        defaults={
            'name_en': name_en,
            'name_ru': name_ru,
            'name_kz': name_kz,
        }
    )
    categories.append(cat)
print('✓ Categories created')

# Create tags
tags = []
for name in ['Python', 'Django', 'API', 'Tutorial', 'News']:
    tag, _ = Tag.objects.get_or_create(name=name, slug=name.lower())
    tags.append(tag)
print('✓ Tags created')

# Create posts
posts = []
for i in range(1, 26):
    author = random.choice(users)
    category = random.choice(categories)
    post_status = PostStatus.PUBLISHED if i > 5 else PostStatus.DRAFT

    post, created = Post.objects.get_or_create(
        slug=f'sample-post-{i}',
        defaults={
            'title': f'Sample Post {i}',
            'author': author,
            'body': f'This is the body of sample post {i}. ' * 10,
            'category': category,
            'status': post_status,
        }
    )
    if created:
        post.tags.set(random.sample(tags, random.randint(1, 3)))
    posts.append(post)
print('✓ Posts created')

# Create comments (only on the first 20 posts)
for post in posts[:20]:
    for _ in range(random.randint(1, 5)):
        author = random.choice(users)
        Comment.objects.get_or_create(
            post=post,
            author=author,
            defaults={'body': f'This is a comment on {post.title}'},
        )
print('✓ Comments created')
"
echo -e "${GREEN}✓ Database seeded successfully${NC}"

# Start development server
echo -e "\n${YELLOW}Starting development server...${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Blog API is ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "API:          ${GREEN}http://localhost:8000/api/${NC}"
echo -e "Swagger UI:   ${GREEN}http://localhost:8000/api/docs/${NC}"
echo -e "ReDoc:        ${GREEN}http://localhost:8000/api/redoc/${NC}"
echo -e "Admin Panel:  ${GREEN}http://localhost:8000/admin/${NC}"
echo -e "\n${YELLOW}Superuser credentials:${NC}"
echo -e "Email:    admin@example.com"
echo -e "Password: admin123"
echo -e "\n${YELLOW}Test user credentials:${NC}"
echo -e "Email:    testuser1@example.com (testuser2@example.com, etc.)"
echo -e "Password: password123"
echo -e "\n${YELLOW}Press Ctrl+C to stop the server${NC}"
echo -e "${GREEN}========================================${NC}"

python manage.py runserver