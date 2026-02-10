# ML Forecasting Skill

**Purpose**: Build demand forecasting models for retail inventory prediction

**When to use**: Feature engineering, model training, evaluation, deployment

---

## Model Architecture: LSTM + XGBoost Ensemble

### Why Ensemble?
- **LSTM**: Temporal patterns (seasonality, trends, weekly cycles)
- **XGBoost**: Non-linear feature relationships (weather × category, promo × discount)
- **Rules**: Domain knowledge (new items, promotions, seasonal edge cases)
- **Together**: Better than any single model

### Performance Targets
- MAE <15% of actual demand
- MAPE <20%
- 70% of predictions within ±15%
- Inference: <100ms per SKU

---

## Feature Engineering (45 Features Total)

```python
def create_features(sku: str, store_id: str, forecast_date: date) -> dict:
    """Extract 45 features for demand forecasting"""
    
    features = {}
    
    # === TEMPORAL (12 features) ===
    features['day_of_week'] = forecast_date.weekday()  # 0-6
    features['week_of_year'] = forecast_date.isocalendar()[1]  # 1-52
    features['month'] = forecast_date.month  # 1-12
    features['is_weekend'] = 1 if forecast_date.weekday() >= 5 else 0
    features['is_holiday'] = check_holiday(forecast_date)
    features['days_to_next_holiday'] = get_days_to_next_holiday(forecast_date)
    features['days_since_last_holiday'] = get_days_since_last_holiday(forecast_date)
    features['is_month_start'] = 1 if forecast_date.day <= 7 else 0
    features['is_month_end'] = 1 if forecast_date.day >= 24 else 0
    features['season'] = get_season(forecast_date.month)  # 0-3
    features['is_payday_week'] = check_payday_week(forecast_date)  # 1st, 15th
    features['days_in_month'] = calendar.monthrange(forecast_date.year, forecast_date.month)[1]
    
    # === SALES HISTORY (15 features) ===
    sales_history = get_sales_history(sku, store_id, days=90)
    features['avg_sales_7d'] = sales_history[-7:].mean()
    features['avg_sales_14d'] = sales_history[-14:].mean()
    features['avg_sales_30d'] = sales_history[-30:].mean()
    features['avg_sales_90d'] = sales_history.mean()
    features['std_sales_30d'] = sales_history[-30:].std()
    features['cv_sales_30d'] = features['std_sales_30d'] / (features['avg_sales_30d'] + 1e-6)
    features['sales_trend_30d'] = calculate_linear_trend(sales_history[-30:])
    features['sales_same_day_last_week'] = sales_history[-7] if len(sales_history) >= 7 else 0
    features['sales_same_day_last_month'] = sales_history[-30] if len(sales_history) >= 30 else 0
    features['max_sales_90d'] = sales_history.max()
    features['min_sales_90d'] = sales_history.min()
    features['days_since_last_sale'] = get_days_since_last_sale(sku, store_id)
    features['weekend_weekday_ratio'] = calculate_weekend_ratio(sales_history)
    features['first_week_vs_other_ratio'] = calculate_first_week_ratio(sales_history)
    features['sales_volatility_30d'] = features['std_sales_30d'] / (features['avg_sales_30d'] + 1e-6)
    
    # === PRODUCT (6 features) ===
    product = get_product(sku)
    features['category_encoded'] = encode_category(product.category)  # 0-N
    features['price'] = product.retail_price
    features['price_vs_category_avg'] = product.retail_price / get_category_avg_price(product.category)
    features['is_perishable'] = 1 if product.shelf_life_days < 7 else 0
    features['is_national_brand'] = 1 if product.brand_type == 'national' else 0
    features['seasonality_index'] = get_seasonality_index(product.category, forecast_date.month)
    
    # === STORE (5 features) ===
    store = get_store(store_id)
    features['store_sqft'] = store.square_footage
    features['store_type_urban'] = 1 if store.type == 'urban' else 0
    features['population_density'] = get_population_density(store.zip)
    features['median_income'] = get_median_income(store.zip)
    features['distance_to_competitor_miles'] = get_distance_to_nearest_competitor(store)
    
    # === PROMOTIONS (4 features) ===
    promo = get_active_promotion(sku, store_id, forecast_date)
    features['has_promotion'] = 1 if promo else 0
    features['discount_pct'] = promo.discount_pct if promo else 0
    features['days_into_promotion'] = get_days_into_promo(promo) if promo else 0
    features['days_since_last_promotion'] = get_days_since_last_promo(sku, store_id)
    
    # === WEATHER (3 features) ===
    weather = get_weather_forecast(store_id, forecast_date)
    features['temp_forecast'] = weather.temperature
    features['precip_prob'] = weather.precipitation_probability
    features['weather_impact_score'] = calculate_weather_impact(product.category, weather)
    
    return features
```

---

## Model Training Pipeline

### Step 1: Data Preparation

```python
def prepare_training_data(customer_id: str, lookback_days: int = 365):
    """Extract training data for all SKU×store combinations"""
    
    # Query transactions
    query = """
        SELECT 
            product_id,
            store_id,
            DATE(timestamp) as date,
            SUM(quantity) as quantity_sold
        FROM transactions
        WHERE customer_id = %s
            AND timestamp >= NOW() - INTERVAL '%s days'
        GROUP BY product_id, store_id, DATE(timestamp)
        ORDER BY product_id, store_id, date
    """
    
    data = pd.read_sql(query, engine, params=[customer_id, lookback_days])
    
    # Fill missing dates with 0 sales
    data = fill_missing_dates(data)
    
    # Feature engineering
    features_list = []
    for (product_id, store_id), group in data.groupby(['product_id', 'store_id']):
        for idx, row in group.iterrows():
            features = create_features(
                sku=get_sku_from_product_id(product_id),
                store_id=store_id,
                forecast_date=row['date']
            )
            features['target'] = row['quantity_sold']
            features_list.append(features)
    
    df = pd.DataFrame(features_list)
    
    # Train/validation split (time-based, last 60 days = validation)
    split_date = datetime.now() - timedelta(days=60)
    train_df = df[df['forecast_date'] < split_date]
    val_df = df[df['forecast_date'] >= split_date]
    
    X_train = train_df.drop(['target', 'forecast_date'], axis=1)
    y_train = train_df['target']
    X_val = val_df.drop(['target', 'forecast_date'], axis=1)
    y_val = val_df['target']
    
    return X_train, y_train, X_val, y_val
```

### Step 2: Train LSTM

```python
import tensorflow as tf

def build_lstm_model(sequence_length=30, n_features=45):
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(128, return_sequences=True, 
                             input_shape=(sequence_length, n_features)),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.LSTM(64, return_sequences=False),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(7)  # 7-day forecast
    ])
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae', 'mape']
    )
    
    return model

def train_lstm(X_train, y_train, X_val, y_val):
    model = build_lstm_model()
    
    # Reshape for LSTM (samples, timesteps, features)
    X_train_seq = create_sequences(X_train, sequence_length=30)
    X_val_seq = create_sequences(X_val, sequence_length=30)
    
    # Train
    history = model.fit(
        X_train_seq, y_train,
        validation_data=(X_val_seq, y_val),
        epochs=50,
        batch_size=64,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=3)
        ]
    )
    
    return model, history
```

### Step 3: Train XGBoost

```python
import xgboost as xgb

def train_xgboost(X_train, y_train, X_val, y_val):
    model = xgb.XGBRegressor(
        objective='reg:squarederror',
        n_estimators=500,
        learning_rate=0.03,
        max_depth=8,
        subsample=0.8,
        colsample_bytree=0.8,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=20,
        verbose=False
    )
    
    return model
```

### Step 4: Ensemble + Rules

```python
def predict_with_ensemble(sku: str, store_id: str, days_ahead: int = 7):
    """Ensemble prediction with business rules"""
    
    # Get features
    features = create_features(sku, store_id, date.today())
    
    # Model predictions
    lstm_pred = lstm_model.predict(prepare_sequence(features))
    xgb_pred = xgb_model.predict([features] * days_ahead)
    
    # Weighted ensemble (tuned on validation set)
    ensemble_pred = 0.35 * lstm_pred + 0.65 * xgb_pred
    
    # Business rules adjustments
    context = {
        'days_of_data': get_days_of_data(sku, store_id),
        'has_promotion': features['has_promotion'],
        'discount_pct': features['discount_pct'],
        'is_seasonal': features['seasonality_index'] > 0.7,
        'in_season': check_if_in_season(sku, date.today())
    }
    
    adjusted_pred = apply_business_rules(ensemble_pred, context)
    
    # Confidence intervals
    historical_mae = get_model_mae(sku, store_id)
    lower = adjusted_pred - (1.96 * historical_mae)
    upper = adjusted_pred + (1.96 * historical_mae)
    
    return {
        'forecast': adjusted_pred,
        'lower_bound': max(0, lower),
        'upper_bound': upper,
        'confidence': 0.95
    }

def apply_business_rules(forecast: float, context: dict) -> float:
    """Domain knowledge adjustments"""
    adjusted = forecast
    
    # Rule 1: New item (< 30 days data)
    if context['days_of_data'] < 30:
        category_avg = get_category_average_sales(context['category'])
        adjusted = category_avg * 0.7  # New items start slower
    
    # Rule 2: Promotion lift
    if context['has_promotion']:
        lift_factor = 1 + (context['discount_pct'] / 10)
        adjusted = forecast * lift_factor
    
    # Rule 3: Seasonal out of season
    if context['is_seasonal'] and not context['in_season']:
        adjusted = forecast * 0.1  # Halloween candy in November
    
    return adjusted
```

---

## Model Evaluation

```python
def evaluate_model(model, X_test, y_test):
    """Calculate performance metrics"""
    
    predictions = model.predict(X_test)
    
    # Mean Absolute Error
    mae = np.mean(np.abs(predictions - y_test))
    
    # Mean Absolute Percentage Error
    mape = np.mean(np.abs((y_test - predictions) / (y_test + 1e-6))) * 100
    
    # R-squared
    r2 = r2_score(y_test, predictions)
    
    # Coverage (% within ±15%)
    within_15_pct = np.mean(np.abs((predictions - y_test) / (y_test + 1e-6)) <= 0.15) * 100
    
    # Bias (over-forecast vs under-forecast)
    bias = np.mean(predictions - y_test) / np.mean(y_test) * 100
    
    return {
        'mae': mae,
        'mape': mape,
        'r2': r2,
        'coverage_15pct': within_15_pct,
        'bias_pct': bias
    }

# Target thresholds
ACCEPTABLE_PERFORMANCE = {
    'mae_pct': 15,  # MAE < 15% of average demand
    'mape': 20,     # MAPE < 20%
    'coverage': 70, # 70% within ±15%
    'bias': 5       # Bias within ±5%
}
```

---

## Deployment to Vertex AI

```python
from google.cloud import aiplatform

def deploy_to_vertex_ai(model_path: str, model_name: str):
    """Deploy trained model to Vertex AI"""
    
    # Upload model
    model = aiplatform.Model.upload(
        display_name=model_name,
        artifact_uri=model_path,
        serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-11:latest"
    )
    
    # Create endpoint
    endpoint = aiplatform.Endpoint.create(display_name=f"{model_name}-endpoint")
    
    # Deploy with autoscaling
    model.deploy(
        endpoint=endpoint,
        machine_type="n1-standard-4",
        min_replica_count=1,
        max_replica_count=5,
        traffic_percentage=100
    )
    
    return endpoint

# Batch prediction for all SKUs
def batch_predict(customer_id: str, forecast_date: date):
    """Generate forecasts for all active SKUs"""
    
    skus = get_active_skus(customer_id)
    stores = get_active_stores(customer_id)
    
    forecasts = []
    for sku in skus:
        for store in stores:
            forecast = predict_with_ensemble(sku, store.id, days_ahead=7)
            forecasts.append({
                'customer_id': customer_id,
                'store_id': store.id,
                'sku': sku,
                'forecast_date': forecast_date,
                'forecasted_demand': forecast['forecast'],
                'confidence_lower': forecast['lower_bound'],
                'confidence_upper': forecast['upper_bound']
            })
    
    # Bulk insert
    insert_forecasts(forecasts)
```

---

## Monitoring & Retraining

```python
# Weekly retraining (Celery task)
@celery.task
def weekly_model_retraining(customer_id: str):
    """Retrain models with new data"""
    
    # Prepare data
    X_train, y_train, X_val, y_val = prepare_training_data(customer_id)
    
    # Train new models
    new_lstm = train_lstm(X_train, y_train, X_val, y_val)
    new_xgb = train_xgboost(X_train, y_train, X_val, y_val)
    
    # Evaluate
    lstm_metrics = evaluate_model(new_lstm, X_val, y_val)
    xgb_metrics = evaluate_model(new_xgb, X_val, y_val)
    
    # Compare to current production model
    current_mae = get_production_model_mae(customer_id)
    new_mae = (lstm_metrics['mae'] + xgb_metrics['mae']) / 2
    
    # Deploy if better
    if new_mae < current_mae:
        deploy_model(new_lstm, new_xgb, version=f"v{get_next_version()}")
        log_deployment(customer_id, new_mae, improvement=current_mae - new_mae)
    else:
        log_rejection(customer_id, reason="No improvement")
```

---

## DO / DON'T

### DO
- ✅ Use ensemble (better than single model)
- ✅ Feature engineering (45 features beat raw data)
- ✅ Time-based split (last N days = validation)
- ✅ Apply business rules (handle edge cases)
- ✅ Monitor performance (retrain when degrades)
- ✅ Calculate confidence intervals (show uncertainty)

### DON'T
- ❌ Random train/test split (leaks future info)
- ❌ Overfit on training data (use validation set)
- ❌ Deploy without evaluation (check MAE, MAPE)
- ❌ Ignore domain knowledge (rules matter)
- ❌ Train on all data (save some for validation)

---

**Last Updated**: 2026-02-09  
**Version**: 1.0.0
