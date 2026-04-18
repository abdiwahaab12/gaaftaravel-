# 🚀 Quick Deployment Guide

## 🌟 Deploy Your Wanaag Travel Website Online

### Option 1: Heroku (Easiest - 5 minutes)

1. **Install Heroku CLI**
   - Download from: https://devcenter.heroku.com/articles/heroku-cli
   - Install and restart your terminal

2. **Run the deployment script**
   ```bash
   python deploy.py
   ```
   - Choose option 1 (Heroku)
   - Follow the prompts
   - Your website will be live in minutes!

3. **Manual Heroku deployment**
   ```bash
   # Login to Heroku
   heroku login
   
   # Create app
   heroku create your-app-name
   
   # Set environment variables
   heroku config:set DB_HOST=your_database_host
   heroku config:set DB_USER=your_database_user
   heroku config:set DB_PASSWORD=your_database_password
   heroku config:set DB_NAME=your_database_name
   heroku config:set JWT_SECRET_KEY=your_secret_key
   heroku config:set FLASK_ENV=production
   
   # Deploy
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

### Option 2: Railway (GitHub Integration)

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Deploy on Railway**
   - Go to https://railway.app
   - Sign up with GitHub
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Add environment variables in Railway dashboard
   - Deploy!

### Option 3: Render (Free Tier Available)

1. **Push to GitHub** (same as Railway)

2. **Deploy on Render**
   - Go to https://render.com
   - Sign up with GitHub
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn App:app`
   - Add environment variables
   - Deploy!

## 🗄️ Database Setup

### For Heroku:
- Add ClearDB MySQL addon: `heroku addons:create cleardb:ignite`
- Get database URL: `heroku config:get CLEARDB_DATABASE_URL`

### For Railway:
- Add MySQL service in Railway dashboard
- Use the provided connection details

### For Render:
- Use external MySQL service like PlanetScale or Aiven
- Add connection details as environment variables

## 🔧 Environment Variables

Set these in your hosting platform:

```
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=your_database_name
JWT_SECRET_KEY=your_jwt_secret_key
FLASK_ENV=production
```

## 📱 Access Your Website

After deployment, your website will be available at:
- **Heroku**: `https://your-app-name.herokuapp.com`
- **Railway**: `https://your-app-name.railway.app`
- **Render**: `https://your-app-name.onrender.com`

## 🆘 Need Help?

1. Check the full `DEPLOYMENT_GUIDE.md` for detailed instructions
2. Check your hosting platform's documentation
3. Look at the logs in your hosting platform's dashboard

## 🎉 Success!

Once deployed, your Wanaag Travel & Logistics website will be live and accessible from anywhere in the world!

**Default Login:**
- Email: admin@wanaagtravel.com
- Password: admin123
