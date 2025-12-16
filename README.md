SafeRoute AI is a crime-aware route recommendation system that prioritizes user safety by analyzing historical crime data along with route information. Instead of suggesting only the shortest path, the system uses machine learning to assign safety scores and recommend safer travel routes.

Objectives

Provide safer navigation using crime data analysis

Assign safety scores to routes using machine learning

Visualize safe and unsafe routes in real time

Tech Stack

Languages: Python, JavaScript, HTML, CSS

Libraries & Frameworks: TensorFlow, Keras, OpenCV, Flask (REST APIs), Streamlit, NumPy, Pandas, Scikit-learn

Database: MongoDB

APIs & Tools: Mapbox API, Git, GitHub, Postman

System Architecture

User enters source and destination

Routes are fetched using Mapbox API

Crime data is retrieved from MongoDB

Machine learning model computes route safety scores

Safer routes are ranked and displayed on the map

Features

Crime-based route safety analysis

Machine learning-powered safety scoring

Severity-based crime weighting

RESTful API architecture

Interactive map visualization

Machine Learning Methodology

Preprocessing of historical crime data

Feature extraction based on crime type and frequency

Regression model to generate continuous safety scores

Ranking of routes based on predicted safety levels

Evaluation Metrics

Mean Absolute Error (MAE)

Mean Squared Error (MSE)

R² Score

Project Structure
SafeRoute-AI/
├── backend/
│   ├── app.py
│   ├── routes/
│   ├── models/
│   └── config.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── script.js
├── data/
│   └── crime_data.csv
├── models/
│   └── safety_model.pkl
└── README.md

How to Run the Project

Clone the repository

git clone https://github.com/your-username/SafeRoute-AI.git


Install required dependencies

pip install -r requirements.txt


Start the backend server

python backend/app.py


Open the frontend in a web browser

Use Cases

Safer daily commuting

Women safety applications

Smart city navigation systems

Future Enhancements

Integration of real-time crime data

Mobile application support

Personalized safety preferences

Emergency alert and SOS features

Conclusion

SafeRoute AI demonstrates how machine learning and geospatial data can be effectively combined to address real-world safety challenges. The system provides safer route recommendations by prioritizing security over distance.
