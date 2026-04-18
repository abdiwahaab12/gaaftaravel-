# Wanaag Travel & Logistics - Deployment Guide

## 🚀 Online Deployment Options

### Option 1: Heroku (Recommended for beginners)
1. **Create Heroku Account**: Go to [heroku.com](https://heroku.com) and sign up
2. **Install Heroku CLI**: Download from [devcenter.heroku.com](https://devcenter.heroku.com/articles/heroku-cli)
3. **Deploy Steps**:
   ```bash
   # Login to Heroku
   heroku login
   
   # Create new app
   heroku create wanaag-travel-app
   
   # Set environment variables
   heroku config:set DB_HOST=your_database_host
   heroku config:set DB_USER=your_database_user
   heroku config:set DB_PASSWORD=your_database_password
   heroku config:set DB_NAME=your_database_name
   heroku config:set JWT_SECRET_KEY=your_jwt_secret_key
   heroku config:set SECRET_KEY=your_flask_secret_key
   
   # Deploy
   git add .
   git commit -m "Initial deployment"
   git push heroku main
   ```

### Option 2: Railway
1. **Create Railway Account**: Go to [railway.app](https://railway.app)
2. **Connect GitHub**: Link your GitHub repository
3. **Deploy**: Railway will automatically deploy from your GitHub repo
4. **Set Environment Variables**: Add your database and JWT secrets in Railway dashboard

### Option 3: Render
1. **Create Render Account**: Go to [render.com](https://render.com)
2. **New Web Service**: Connect your GitHub repository
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `gunicorn App:app`
5. **Set Environment Variables**: Add your database and JWT secrets

### Option 4: PythonAnywhere
1. **Create Account**: Go to [pythonanywhere.com](https://pythonanywhere.com)
2. **Upload Files**: Upload your project files
3. **Create Web App**: Choose Flask and point to your App.py
4. **Set Environment Variables**: Add your database and JWT secrets

## 🗄️ Database Options

### Option 1: MySQL (Recommended)
- **Heroku**: Use ClearDB MySQL addon
- **Railway**: Use MySQL service
- **Render**: Use external MySQL service like PlanetScale
- **PythonAnywhere**: Use their MySQL database

### Option 2: PostgreSQL
- **Heroku**: Use Heroku Postgres addon
- **Railway**: Use PostgreSQL service
- **Render**: Use external PostgreSQL service

## 🔧 Environment Variables Setup

Create a `.env` file with these variables:
```
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=your_database_name
JWT_SECRET_KEY=your_jwt_secret_key
SECRET_KEY=your_flask_secret_key
```

## 📁 Project Structure
```
updated_frontend/
├── App.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Procfile              # Heroku deployment file
├── runtime.txt           # Python version
├── static/               # Static files (CSS, JS, images)
├── templates/            # HTML templates
└── database.db           # SQLite database (for development)
```

## 🚀 Quick Deploy to Heroku

1. **Install Heroku CLI**
2. **Login**: `heroku login`
3. **Create App**: `heroku create your-app-name`
4. **Set Config**: Copy environment variables from env_example.txt
5. **Deploy**: 
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

## 🔍 Troubleshooting

### Common Issues:
1. **Database Connection**: Make sure your database is accessible from the hosting platform
2. **Static Files**: Ensure all static files are in the `static/` folder
3. **Environment Variables**: Double-check all environment variables are set
4. **Python Version**: Make sure the Python version in runtime.txt is supported

### Logs:
- **Heroku**: `heroku logs --tail`
- **Railway**: Check logs in dashboard
- **Render**: Check logs in dashboard

## 📞 Support
If you need help with deployment, check the hosting platform's documentation or contact support.
