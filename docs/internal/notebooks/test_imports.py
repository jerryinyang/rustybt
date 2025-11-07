#!/usr/bin/env python3
"""
Test script to verify all imports from fixed notebooks are correct.
"""

print("Testing imports from corrected notebooks...")
print("=" * 60)

# Test Notebook 15 imports (Monte Carlo)
print("\n📋 Notebook 15: Monte Carlo Basics")
print("-" * 60)

try:
    from rustybt.optimization.monte_carlo import (
        MonteCarloResult,
        MonteCarloSimulator,
    )

    print("✅ MonteCarloSimulator - imported successfully")
    print("✅ MonteCarloResult - imported successfully")

    # Verify MonteCarloSimulator has run() method
    assert hasattr(MonteCarloSimulator, "run"), "MonteCarloSimulator should have run() method"
    print("✅ MonteCarloSimulator.run() method exists")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)

try:
    from rustybt.optimization.noise_infusion import (
        NoiseInfusionResult,
        NoiseInfusionSimulator,
    )

    print("✅ NoiseInfusionSimulator - imported successfully")
    print("✅ NoiseInfusionResult - imported successfully")

    # Verify NoiseInfusionSimulator has run() method
    assert hasattr(NoiseInfusionSimulator, "run"), "NoiseInfusionSimulator should have run() method"
    print("✅ NoiseInfusionSimulator.run() method exists")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)

# Test Notebook 16 imports (Sensitivity Analysis)
print("\n📋 Notebook 16: Sensitivity Analysis Basics")
print("-" * 60)

try:
    from rustybt.optimization.sensitivity import (
        InteractionResult,
        SensitivityAnalyzer,
        SensitivityResult,
    )

    print("✅ SensitivityAnalyzer - imported successfully")
    print("✅ SensitivityResult - imported successfully")
    print("✅ InteractionResult - imported successfully")

    # Verify SensitivityAnalyzer has required methods
    assert hasattr(
        SensitivityAnalyzer, "analyze"
    ), "SensitivityAnalyzer should have analyze() method"
    print("✅ SensitivityAnalyzer.analyze() method exists")

    assert hasattr(
        SensitivityAnalyzer, "analyze_interaction"
    ), "SensitivityAnalyzer should have analyze_interaction() method"
    print("✅ SensitivityAnalyzer.analyze_interaction() method exists")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)

# Test Notebook 19 imports (Portfolio Allocation) - should already be correct
print("\n📋 Notebook 19: Portfolio Allocation Methods")
print("-" * 60)

try:
    from rustybt.portfolio import (
        AllocationRebalancer,
        DrawdownBasedAllocation,
        DynamicAllocation,
        FixedAllocation,
        KellyCriterionAllocation,
        PortfolioAllocator,
        RebalancingFrequency,
        RiskParityAllocation,
    )

    print("✅ PortfolioAllocator - imported successfully")
    print("✅ FixedAllocation - imported successfully")
    print("✅ DynamicAllocation - imported successfully")
    print("✅ RiskParityAllocation - imported successfully")
    print("✅ KellyCriterionAllocation - imported successfully")
    print("✅ DrawdownBasedAllocation - imported successfully")
    print("✅ AllocationRebalancer - imported successfully")
    print("✅ RebalancingFrequency - imported successfully")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)

# Final summary
print("\n" + "=" * 60)
print("✅ ALL IMPORTS VERIFIED SUCCESSFULLY!")
print("=" * 60)
print("\nSummary:")
print("  ✅ Notebook 15 (Monte Carlo): All imports correct")
print("  ✅ Notebook 16 (Sensitivity Analysis): All imports correct")
print("  ✅ Notebook 19 (Portfolio Allocation): All imports correct")
print("\nAll API corrections have been validated against actual code!")
