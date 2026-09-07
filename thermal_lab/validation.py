"""Numerical validation shared by camera frames and recordings."""
import math

class ValidationError(ValueError):
    pass

def finite(value, label, low, high):
    if isinstance(value, bool):
        raise ValidationError(f'{label} must be a number')
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(f'{label} must be a number') from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValidationError(f'{label} must be between {low} and {high}')
    return value

def integer(value,label,low,high):
    n=finite(value,label,low,high)
    if int(n)!=n:raise ValidationError(label+' must be an integer')
    return int(n)
