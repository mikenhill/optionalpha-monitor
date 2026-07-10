#!/usr/bin/env python3
"""Get PCA feature loadings to explain what each PC represents."""

import json
import requests

# Get PCA data from API
response = requests.get('http://localhost:5050/api/pca')
data = response.json()

print("=== Top 3 Principal Components Explained ===\n")

for comp in data['components'][:3]:
    pc = comp['pc']
    variance = comp['variance']
    cumulative = comp['cumulative']
    
    print(f"PC{pc}: {variance:.1%} variance (cumulative: {cumulative:.1%})")
    print("Top contributing features:")
    
    # Group by positive/negative loadings
    positive = [f for f in comp['top_features'] if f['loading'] > 0]
    negative = [f for f in comp['top_features'] if f['loading'] < 0]
    
    if positive:
        print("  Positive loadings (moves together):")
        for feat in positive[:5]:
            print(f"    {feat['feature']:20s}: {feat['loading']:+.3f}")
    
    if negative:
        print("  Negative loadings (moves opposite):")
        for feat in negative[:3]:
            print(f"    {feat['feature']:20s}: {feat['loading']:+.3f}")
    
    # Interpret what this PC represents
    if pc == 1:
        print("  → PC1 represents: **Overall Call Dominance** - Bullish gamma exposure when high")
    elif pc == 2:
        print("  → PC2 represents: [Check loadings to determine]")
    elif pc == 3:
        print("  → PC3 represents: [Check loadings to determine]")
    
    print()
