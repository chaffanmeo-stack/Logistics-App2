"""Fare calculation — volumetric weight vs actual weight. Dimensions are
optional; if left at 0, only actual weight + distance matter."""

VOLUMETRIC_DIVISOR = 5000
BASE_FARE_PKR = 150.0
PER_KG_PKR = 50.0
PER_KM_PKR = 2.0


def calculate_fare(weight_kg: float, distance_km: float, length_cm: float = 0, width_cm: float = 0, height_cm: float = 0) -> float:
    volumetric_weight = (length_cm * width_cm * height_cm) / VOLUMETRIC_DIVISOR
    billable_weight = max(weight_kg, volumetric_weight)
    fare = BASE_FARE_PKR + (billable_weight * PER_KG_PKR) + (distance_km * PER_KM_PKR)
    return round(fare, 2)
