from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_babelex import format_datetime
import pytz 
import os
from flask import Flask, render_template
from flask_babelex import format_datetime
from flask_bootstrap import Bootstrap
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from collections import OrderedDict
import logging
import math

load_dotenv()
app = Flask(__name__, template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://")
db = SQLAlchemy(app)
Bootstrap(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    total_engagement = db.Column(db.Integer, default=0)
class Tweet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('tweets', lazy=True))
    content = db.Column(db.String(280))
    likes = db.Column(db.Integer)
    retweets = db.Column(db.Integer)
    replies = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
class FetchTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('fetch_times', lazy=True))
    last_fetched = db.Column(db.DateTime)
    tweet_increase = db.Column(db.Integer)
class TotalIncrease(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True))
    total_tweet_engagement = db.Column(db.Integer)
try:
    with app.app_context():
        # Create the database tables
        db.create_all()
except Exception as e:
    print(f"Database error: {str(e)}")

def calculate_engagement(tweet):
    likes = tweet.likes
    retweets = tweet.retweets
    replies = tweet.replies
    
    # Define weights based on the importance you assign to each metric
    weights = {'likes': 1, 'retweets': 2, 'replies': 1.5}
    
    # Calculate the time decay factor based on the age of the tweet
    hours_since_tweet = (datetime.utcnow() - tweet.timestamp).total_seconds() / 3600
    decay_factor = 0.5 ** (hours_since_tweet / 3)  # Half-life of 3 hours
    
    engagement_score = (likes*weights['likes'] + retweets*weights['retweets'] + replies*weights['replies']) * decay_factor
    
    return engagement_score

def calculate_normalized_engagement(total_engagement, num_tweets, followers, time_window=24):
    # Calculate the average tweets per day
    avg_tweets_per_day = num_tweets / time_window
    
    # Define a weight for the time factor based on your specific needs
    time_weight = 0.5
    
    # Adjust the total engagement with the time factor
    adjusted_engagement = total_engagement * (1 + time_weight * avg_tweets_per_day)
    
    normalized_engagement = float(adjusted_engagement / followers)
    
    return normalized_engagement

from datetime import datetime, timedelta

def get_current_engagement(max_possible_engagement):
    # Define the groups
    groups = {
        'La grieta': ['SergioChouza', 'atilioboron'],
        'Política': ['lilialemoine', 'CarlosMaslaton', 'MabelPajarita'],
        'Medios': ['alexcaniggia', 'yanilatorre', 'rialjorge']
    }

    # Define the followers for each group
    group_followers = {
        'La grieta': 128000 + 92000,
        'Política': 350000 + 78000 + 90000,
        'Medios': 3300000 + 1300000 + 340000
    }

    # Initialize a dictionary to store group engagements
    group_engagements = {group: 0 for group in groups}

    # Calculate total engagement for all groups
    a_day_ago = datetime.utcnow() - timedelta(days=1)
    for group, users in groups.items():
        for user_name in users:
            user = User.query.filter_by(name=user_name).first()
            if user:
                recent_tweets = Tweet.query.filter(Tweet.user_id == user.id, Tweet.timestamp >= a_day_ago).all()
                engagements = [calculate_engagement(tweet) for tweet in recent_tweets]
                total_engagement = sum(engagements)
                max_engagement = max(engagements) if engagements else 0
                if recent_tweets:
                    normalized_engagement = calculate_normalized_engagement(total_engagement, max_engagement, len(recent_tweets), group_followers[group]) / max_possible_engagement
                    group_engagements[group] += normalized_engagement

    # Sort the dictionary by engagement in descending order
    sorted_group_engagements = sorted(group_engagements.items(), key=lambda x: x[1], reverse=True)
    print(sorted_group_engagements) 
    return sorted_group_engagements



def get_engagement_by_groups(groups, group_followers, max_possible_engagement):
    a_day_ago = datetime.utcnow() - timedelta(days=1)
    group_engagements = {group: 0 for group in groups}

    # Calculate total engagement for all groups
    for group_name, users in groups.items():
        total_engagement = 0
        for user_name in users:
            user = User.query.filter_by(name=user_name).first()
            if user:
                recent_tweets = Tweet.query.filter(Tweet.user_id == user.id, Tweet.timestamp >= a_day_ago).all()
                for tweet in recent_tweets:
                    engagement = calculate_engagement(tweet)
                    normalized_engagement = calculate_normalized_engagement(engagement, max_possible_engagement, len(recent_tweets), group_followers[group_name]) / max_possible_engagement
                    total_engagement += normalized_engagement

        group_engagements[group_name] = total_engagement

    # Sort the dictionary by engagement in descending order
    sorted_group_engagements = sorted(group_engagements.items(), key=lambda x: x[1], reverse=True)

    return sorted_group_engagements




@app.route('/engagement_by_groups', methods=['POST'])
def engagement_by_groups_route():
    # Define the maximum possible engagement score
    max_possible_engagement = 100000.0 

    # Get the groups from the request body
    groups = request.json['groups']

    # Define the followers for each group
    group_followers = {
        'La grieta': 128000 + 92000,
        'Política': 350000 + 78000 + 90000,
        'Medios': 3300000 + 1300000 + 340000
    }

    # Get the engagement data for the chosen groups
    group_engagements = get_engagement_by_groups(groups, group_followers, max_possible_engagement)
    print(group_engagements) 
    return jsonify(group_engagements)


@app.route('/')
def index():

    max_possible_engagement = 100000.0 

    # Get current engagement
    group_engagements = get_current_engagement(max_possible_engagement)

    # Fetch the latest TotalIncrease
    last_total_increase = TotalIncrease.query.order_by(TotalIncrease.timestamp.desc()).first()
    
    # Get total increases in the last 6 hours
    six_hours_ago = datetime.now() - timedelta(hours=6)
    total_increases = TotalIncrease.query.filter(TotalIncrease.timestamp >= six_hours_ago).order_by(TotalIncrease.timestamp.desc()).all()

    # Calculate the average engagement over the past 6 hours
    average_engagement = sum([increase.total_tweet_engagement for increase in total_increases]) / len(total_increases) if total_increases else 0

    # Check for peak occurrences
    peak_occurrences = []
    for increase in total_increases:
        if increase.total_tweet_engagement > average_engagement * 1.1:  # 1.5 is an example threshold for "significant" increase
            peak_occurrences.append((increase.timestamp, increase.total_tweet_engagement))

    # Determine if the total tweet engagement is below average, average, or above average
    latest_engagement = total_increases[0].total_tweet_engagement if total_increases else 0
    if latest_engagement < 500000:
        engagement_level = "NO"
    elif latest_engagement < 600000:
        engagement_level = "?"
    else:
        engagement_level = "SÍ"
    
    # Get the tweet with hate speech content
    hate_tweet = Tweet.query.filter(Tweet.content.isnot(None)).order_by(Tweet.id.desc()).first()

    # Check if a hate tweet was found
    if hate_tweet is not None:
        hate_tweet_content = hate_tweet.content
    else:
        hate_tweet_content = None

    return render_template('index.html', timedelta=timedelta, hate_tweet_content=hate_tweet_content, datetime=datetime, pytz=pytz, group_engagements=group_engagements, peak_occurrences=peak_occurrences, engagement_level=engagement_level, last_total_increase=last_total_increase, min=min)







