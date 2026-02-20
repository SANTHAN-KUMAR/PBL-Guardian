"""
Simple ML utility functions for testing PBL Guardian.
"""

import math


def calculate_mean(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


def calculate_variance(numbers):
    if len(numbers) < 2:
        return 0
    mean = calculate_mean(numbers)
    return sum((x - mean) ** 2 for x in numbers) / (len(numbers) - 1)


def calculate_std_dev(numbers):
    return math.sqrt(calculate_variance(numbers))


def normalize_data(numbers):
    if not numbers:
        return []
    min_val = min(numbers)
    max_val = max(numbers)
    if max_val == min_val:
        return [0.0] * len(numbers)
    return [(x - min_val) / (max_val - min_val) for x in numbers]


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def relu(x):
    return max(0, x)


if __name__ == "__main__":
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    print(f"Mean: {calculate_mean(data)}")
    print(f"Std Dev: {calculate_std_dev(data):.2f}")
    print(f"Normalized: {normalize_data(data)}")
    print(f"Sigmoid(0): {sigmoid(0)}")
    print(f"ReLU(-5): {relu(-5)}")
