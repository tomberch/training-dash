# Training Metrics Formulas — Research Document

> Research compiled from primary sources for cycling and endurance training metrics.
> For use in TrainingDash fitness application.

## Table of Contents

1. [Power-Based Metrics](#power-based-metrics)
2. [Heart Rate Metrics](#heart-rate-metrics)
3. [Fatigue Models](#fatigue-models)
4. [Other Metrics](#other-metrics)
5. [Sources](#sources)

---

## Power-Based Metrics

### Normalized Power (NP)

**Source:** Dr. Andrew Coggan, introduced in "Training and Racing with a Power Meter" (2006)

**Purpose:** Represents the physiological "cost" of variable power output, accounting for the fact
that power variability creates more stress than steady-state riding at the same average.

**Formula:**

```
NP = fourth_root( mean( rolling_30s_avg(power)^4 ) )
```

**Step-by-step calculation:**

1. Calculate a 30-second rolling average of power data
2. Raise each averaged value to the 4th power
3. Calculate the mean of those values
4. Take the 4th root of that mean

**Mathematical notation:**

```
NP = ( (1/n) * Σ P̄ᵢ⁴ )^(1/4)

where P̄ᵢ = (1/30) * Σⱼ₌ᵢ₋₂₉ⁱ Pⱼ  (30-second rolling average at second i)
```

**Implementation notes:**
- Use 1-second power data (resample if higher frequency)
- The 30-second window accounts for the ~30s time constant of physiological response
- The 4th power weighting emphasizes high-intensity efforts
- For activities < 30 seconds, NP = average power

---

### Intensity Factor (IF)

**Source:** Dr. Andrew Coggan, "Training and Racing with a Power Meter"

**Purpose:** Expresses how intense a workout was relative to the athlete's threshold power.

**Formula:**

```
IF = NP / FTP
```

**Where:**
- NP = Normalized Power for the session
- FTP = Functional Threshold Power (power sustainable for ~1 hour)

**Interpretation:**
| IF Value | Interpretation |
|----------|----------------|
| < 0.75   | Recovery/easy endurance |
| 0.75-0.85 | Endurance |
| 0.85-0.95 | Tempo |
| 0.95-1.05 | Threshold |
| 1.05-1.15 | VO2max intervals (average) |
| > 1.15   | Neuromuscular/anaerobic |

---

### Training Stress Score (TSS)

**Source:** Dr. Andrew Coggan, TrainingPeaks. Trademark of Peaksware, LLC.

**Purpose:** Quantifies the overall training load of a workout, combining duration and intensity.

**Formula:**

```
TSS = (t × NP × IF) / (FTP × 3600) × 100
```

**Simplified form:**

```
TSS = (t × IF²) / 3600 × 100
```

**Where:**
- t = duration in seconds
- NP = Normalized Power
- IF = Intensity Factor
- FTP = Functional Threshold Power

**Expanded formula:**

```
TSS = (duration_seconds × NP × IF) / (FTP × 3600) × 100
    = (duration_seconds × NP²) / (FTP² × 36)
```

**Reference point:** 1 hour at FTP = 100 TSS

---

### Variability Index (VI)

**Source:** Dr. Andrew Coggan

**Purpose:** Measures how "smooth" or "variable" power output was during a ride.

**Formula:**

```
VI = NP / Average_Power
```

**Interpretation:**
- VI ≈ 1.0: Very steady power (time trial, trainer)
- VI = 1.05-1.15: Typical outdoor ride
- VI > 1.2: Highly variable (criterium, mountain bike)

---

### W' (W-prime) — Anaerobic Work Capacity

**Source:** Dr. Philip Skiba, "W'bal: An Extension of the CP Model" (2012)

**Purpose:** Represents the finite amount of work (in joules/kilojoules) that can be performed
above Critical Power (CP) before exhaustion.

**Definition:**

```
W' = Total work capacity above CP (in joules)
```

**Typical values:** 15-25 kJ for trained cyclists

**Relationship to Critical Power model:**

```
t_lim = W' / (P - CP)

where:
  t_lim = time to exhaustion at power P
  P = constant power output (P > CP)
  CP = Critical Power (similar to FTP)
```

---

### W' Balance (W'bal)

**Source:** Dr. Philip Skiba, "Calculation of Power Output and Quantification of Training
Stress in Distance Runners: The Development of the GOVSS Algorithm" and subsequent papers.

**Purpose:** Tracks the real-time depletion and reconstitution of W' during variable-power exercise.

**Differential equation (Skiba 2012):**

```
W'bal(t) = W' - Σ W'exp(t)

where W'exp depends on whether P(t) > CP or P(t) ≤ CP
```

**Integral formulation (Skiba 2015 refinement):**

```
W'bal(t) = W' - ∫₀ᵗ (P(u) - CP)⁺ du + ∫₀ᵗ (W' - W'bal(u⁻)) / τ_W' × 1_{P(u)<CP} du
```

**Discrete algorithm (practical implementation):**

For each second t:

```
if P(t) > CP:
    W'bal(t) = W'bal(t-1) - (P(t) - CP)  # Depletion
else:
    W'bal(t) = W' - (W' - W'bal(t-1)) × exp(-(CP - P(t)) × Δt / W')  # Reconstitution
```

**Alternative reconstitution model (Skiba integral):**

```
W'bal(t) = W' - Σᵢ W'exp(i) × exp(-(t - tᵢ) / τ_W')

where:
  τ_W' = W' / (CP - P_recovery)  # Time constant for recovery
  W'exp(i) = work above CP in interval i
```

**Key parameters:**
- W' = total anaerobic capacity (determined from testing)
- CP = Critical Power
- τ_W' = reconstitution time constant (~546s per Skiba, but varies with recovery intensity)

---

## Heart Rate Metrics

### TRIMP (Training Impulse)

**Source:** Eric Banister, 1991. "Modeling Elite Athletic Performance"

**Purpose:** Quantifies training load from heart rate data when power is unavailable.

#### Banister TRIMP (Original)

```
TRIMP = duration_minutes × HRr × 0.64 × e^(1.92 × HRr)  [men]
TRIMP = duration_minutes × HRr × 0.86 × e^(1.67 × HRr)  [women]
```

**Where:**
```
HRr = (HR_exercise - HR_rest) / (HR_max - HR_rest)
```

HRr is the Heart Rate Reserve fraction (0 to 1)

#### Edwards TRIMP (Zone-based)

**Source:** Sally Edwards, simplified zone-based approach

```
TRIMP = Σ (time_in_zone × zone_coefficient)

Zone coefficients:
  Zone 1 (50-60% HRmax): 1
  Zone 2 (60-70% HRmax): 2
  Zone 3 (70-80% HRmax): 3
  Zone 4 (80-90% HRmax): 4
  Zone 5 (90-100% HRmax): 5
```

#### Lucia TRIMP

**Source:** Lucia et al., for elite athletes with lactate testing

```
TRIMP = (time_zone1 × 1) + (time_zone2 × 2) + (time_zone3 × 3)

Where zones are defined by lactate thresholds:
  Zone 1: Below VT1 (ventilatory threshold 1)
  Zone 2: Between VT1 and VT2
  Zone 3: Above VT2
```

---

### hrTSS (Heart Rate Training Stress Score)

**Source:** TrainingPeaks, adaptation of TSS for heart rate data

**Purpose:** Provides a TSS-equivalent metric when power data is unavailable.

**Formula:**

```
hrTSS = (duration_hours × hrIF² × 100)
```

**Where:**

```
hrIF = HRr_avg / HRr_LTHR

HRr_avg = (HR_avg - HR_rest) / (HR_max - HR_rest)
HRr_LTHR = (LTHR - HR_rest) / (HR_max - HR_rest)
```

**Simplified (when using %LTHR):**

```
hrTSS = (duration_hours × (%LTHR / 100)² × 100)
```

**Where:**
- LTHR = Lactate Threshold Heart Rate (approximately HR at FTP effort)
- Typically LTHR ≈ 0.93-0.95 × HRmax for trained athletes

**Alternative formula (TrainingPeaks method):**

```
hrTSS = Σ (hrIF(t)² × Δt) / 3600 × 100
```

Calculated per-second and summed, similar to power-based TSS.

---

### Heart Rate Zones Calculation

**Source:** Multiple systems exist; most common are Coggan/Friel and Karvonen methods.

#### Coggan/Friel Zones (% of LTHR)

| Zone | Name | % of LTHR |
|------|------|-----------|
| 1 | Active Recovery | < 81% |
| 2 | Endurance | 81-89% |
| 3 | Tempo | 90-93% |
| 4 | Threshold | 94-99% |
| 5a | VO2max | 100-102% |
| 5b | Anaerobic | 103-106% |
| 5c | Neuromuscular | > 106% |

#### Karvonen Method (Heart Rate Reserve)

```
Target HR = HR_rest + (HR_reserve × intensity%)
HR_reserve = HR_max - HR_rest
```

| Zone | Intensity % HRR |
|------|-----------------|
| 1 | 50-60% |
| 2 | 60-70% |
| 3 | 70-80% |
| 4 | 80-90% |
| 5 | 90-100% |

#### Percentage of Max HR

```
Target HR = HR_max × intensity%
```

| Zone | % HRmax |
|------|---------|
| 1 | 50-60% |
| 2 | 60-70% |
| 3 | 70-80% |
| 4 | 80-90% |
| 5 | 90-100% |

**HR_max estimation (when not tested):**

```
HR_max = 220 - age                    # Traditional (Haskell/Fox)
HR_max = 208 - (0.7 × age)            # Tanaka (2001) - more accurate
HR_max = 211 - (0.64 × age)           # Nes et al. (2013)
```

---

## Fatigue Models

### Performance Manager Chart (PMC) Overview

**Source:** Dr. Andrew Coggan & TrainingPeaks, based on Banister Impulse-Response model (1975)

The PMC models fitness and fatigue as exponentially weighted moving averages of training stress.

---

### CTL (Chronic Training Load) — "Fitness"

**Source:** TrainingPeaks / Coggan

**Purpose:** Represents accumulated fitness, the long-term training adaptation.

**Formula:**

```
CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) / τ_CTL
```

**Exponential decay form:**

```
CTL_today = CTL_yesterday × (1 - 1/τ_CTL) + TSS_today × (1/τ_CTL)
```

**Where:**
- τ_CTL = time constant, typically **42 days**
- TSS_today = Training Stress Score for today (0 if rest day)

**Alternative (exponential moving average):**

```
CTL_today = Σᵢ TSS(i) × e^(-(t - i) / τ_CTL) / Σᵢ e^(-(t - i) / τ_CTL)
```

**Starting CTL:** Initialize to 0 or estimate from recent training history.

---

### ATL (Acute Training Load) — "Fatigue"

**Source:** TrainingPeaks / Coggan

**Purpose:** Represents recent training stress / accumulated fatigue.

**Formula:**

```
ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) / τ_ATL
```

**Exponential decay form:**

```
ATL_today = ATL_yesterday × (1 - 1/τ_ATL) + TSS_today × (1/τ_ATL)
```

**Where:**
- τ_ATL = time constant, typically **7 days**

---

### TSB (Training Stress Balance) — "Form"

**Source:** TrainingPeaks / Coggan

**Purpose:** Predicts readiness to perform. Positive = fresh, negative = fatigued.

**Formula:**

```
TSB = CTL - ATL
```

**Interpretation:**
| TSB Range | State |
|-----------|-------|
| > +25 | Very fresh (possibly detrained) |
| +15 to +25 | Fresh, peak performance window |
| +5 to +15 | Somewhat fresh |
| -10 to +5 | Neutral (good for training) |
| -10 to -30 | Fatigued (building fitness) |
| < -30 | Very fatigued (overreaching risk) |

**Race day targeting:** Aim for TSB of +15 to +25 for important events.

---

### Ramp Rate

**Source:** TrainingPeaks

**Purpose:** Measures how quickly CTL is changing; used to avoid overtraining.

**Formula:**

```
Ramp Rate = CTL_today - CTL_7days_ago
```

**Guidelines:**
- Sustainable increase: 3-7 TSS/week
- Aggressive building: 7-10 TSS/week
- Risk of overtraining: > 10 TSS/week sustained

---

### Banister Impulse-Response Model (Original)

**Source:** Banister et al., 1975

**Purpose:** The foundational model underlying PMC.

**Formula:**

```
Performance(t) = p₀ + k₁ × Fitness(t) - k₂ × Fatigue(t)

where:
  Fitness(t) = Σᵢ w(i) × e^(-(t-i)/τ₁)
  Fatigue(t) = Σᵢ w(i) × e^(-(t-i)/τ₂)
```

**Parameters:**
- p₀ = baseline performance
- k₁, k₂ = scaling factors (k₂ > k₁ typically)
- τ₁ = fitness time constant (~42-45 days)
- τ₂ = fatigue time constant (~7-15 days)
- w(i) = training load on day i

---

## Other Metrics

### Calories from Power

**Source:** First-law thermodynamics, validated by Coggan et al.

**Purpose:** Most accurate calorie estimation when power data is available.

**Formula:**

```
kJ_work = Average_Power(W) × Duration(s) / 1000

Calories = kJ_work / Gross_Efficiency

where Gross_Efficiency ≈ 0.20-0.25 (typically use 0.25 or 25%)
```

**Practical formula:**

```
Calories ≈ kJ_work × 4

(since 1 kJ / 0.25 efficiency ≈ 4 kcal)
```

**More precise:**

```
Calories = (Power_avg × Duration_hours × 3.6) / 0.25
         = Power_avg × Duration_hours × 14.4
```

**Notes:**
- Gross efficiency varies: untrained ~20%, elite ~25%
- This is mechanical work only; doesn't include basal metabolic rate
- More accurate than HR-based estimates for cycling

---

### Calories from Heart Rate

**Source:** Keytel et al. (2005), various metabolic equations

**Purpose:** Estimate energy expenditure when power data unavailable.

**Keytel equation (includes VO2max):**

```
Men:
Calories/min = (-55.0969 + 0.6309 × HR + 0.1988 × weight_kg + 0.2017 × age) / 4.184

Women:
Calories/min = (-20.4022 + 0.4472 × HR - 0.1263 × weight_kg + 0.074 × age) / 4.184
```

**Simplified (without VO2max):**

```
Men:
Calories/min = (0.6309 × HR_avg + 0.1988 × weight_kg + 0.2017 × age - 55.0969) / 4.184

Women:
Calories/min = (0.4472 × HR_avg - 0.1263 × weight_kg + 0.074 × age - 20.4022) / 4.184
```

**Polar/device estimate (common approximation):**

```
Calories = Duration_min × (0.4472 × (HR_avg / HR_max) × VO2max × weight_kg) / 200
```

**Note:** HR-based estimates are less accurate than power, especially for trained athletes.

---

### Efficiency Factor (EF)

**Source:** Joe Friel, "The Cyclist's Training Bible"

**Purpose:** Tracks aerobic fitness improvement by comparing power output to heart rate.

**Formula:**

```
EF = NP / Average_HR
```

**Alternative (for running):**

```
EF = NGP (Normalized Graded Pace) / Average_HR
```

**Usage:**
- Track over time on similar routes/efforts
- Increasing EF indicates improved aerobic efficiency
- Best compared on steady-state endurance efforts

---

### Aerobic Decoupling (Pw:Hr or Pa:Hr)

**Source:** Joe Friel

**Purpose:** Measures cardiac drift during a workout; indicates aerobic fitness level.

**Formula:**

```
Decoupling% = ((EF_first_half - EF_second_half) / EF_first_half) × 100

where:
  EF_first_half = NP_first_half / HR_avg_first_half
  EF_second_half = NP_second_half / HR_avg_second_half
```

**Interpretation:**
| Decoupling | Interpretation |
|------------|----------------|
| < 5% | Well-developed aerobic base |
| 5-10% | Adequate aerobic fitness |
| > 10% | Aerobic base needs work |

**Notes:**
- Best measured during steady-state endurance rides (Zone 2)
- Cardiac drift is normal; <5% indicates aerobic efficiency
- Duration should be 60+ minutes for meaningful measurement

---

### Power Zones (Coggan)

**Source:** Dr. Andrew Coggan, "Training and Racing with a Power Meter"

| Zone | Name | % of FTP | Purpose |
|------|------|----------|---------|
| 1 | Active Recovery | < 55% | Recovery rides |
| 2 | Endurance | 55-75% | Base building |
| 3 | Tempo | 76-90% | Muscular endurance |
| 4 | Threshold | 91-105% | Lactate threshold |
| 5 | VO2max | 106-120% | Aerobic capacity |
| 6 | Anaerobic | 121-150% | Anaerobic capacity |
| 7 | Neuromuscular | > 150% | Sprints, max efforts |

---

### xPower (Exponentially-weighted Power)

**Source:** Dr. Philip Skiba (alternative to NP)

**Formula:**

```
xPower = (Σ (ewma_25s(power)^4) / n)^(1/4)

where ewma_25s uses a 25-second exponential weighted moving average
with time constant τ = 25 seconds
```

**Difference from NP:**
- Uses exponential weighting vs. simple rolling average
- 25s time constant vs. 30s window
- Slightly different response to power variability

---

## Sources

### Primary Sources

1. **Coggan, A.R. & Allen, H.** (2010). *Training and Racing with a Power Meter* (2nd ed.). VeloPress.
   - Normalized Power, IF, TSS, VI, Power Zones

2. **Coggan, A.R.** (2003). "Training and racing using a power meter: an introduction." 
   - Original NP algorithm description

3. **Skiba, P.F., et al.** (2012). "Modeling the expenditure and reconstitution of work capacity above critical power." *Medicine & Science in Sports & Exercise*, 44(8), 1526-1532.
   - W'bal algorithm

4. **Skiba, P.F., et al.** (2015). "Validation of a novel intermittent W' model for cycling using field data." *International Journal of Sports Physiology and Performance*, 10(6), 672-678.
   - W'bal refinements

5. **Banister, E.W., et al.** (1975). "A systems model of training for athletic performance." *Australian Journal of Sports Medicine*, 7, 57-61.
   - Original Impulse-Response model (CTL/ATL foundation)

6. **Banister, E.W.** (1991). "Modeling Elite Athletic Performance." In *Physiological Testing of Elite Athletes*. Human Kinetics.
   - TRIMP formula

7. **Friel, J.** (2009). *The Cyclist's Training Bible* (4th ed.). VeloPress.
   - Efficiency Factor, Aerobic Decoupling, HR zones

8. **TrainingPeaks** - Official documentation
   - TSS, CTL, ATL, TSB, hrTSS implementation details
   - https://www.trainingpeaks.com/learn/articles/

9. **Tanaka, H., et al.** (2001). "Age-predicted maximal heart rate revisited." *Journal of the American College of Cardiology*, 37(1), 153-156.
   - HR max formula

10. **Keytel, L.R., et al.** (2005). "Prediction of energy expenditure from heart rate monitoring during submaximal exercise." *Journal of Sports Sciences*, 23(3), 289-297.
    - HR-based calorie formulas

### Implementation References

- **Golden Cheetah** (open source): https://github.com/GoldenCheetah/GoldenCheetah
  - Reference implementations for most metrics

- **Xert** (commercial): Proprietary XSS (Xert Strain Score) system
  - Alternative training load metric using MPA (Maximal Power Available)

---

## Implementation Notes for TrainingDash

### Priority Order for Implementation

1. **High Priority (Core Metrics)**
   - NP, IF, TSS (power-based training load)
   - CTL, ATL, TSB (fitness/fatigue tracking)
   - Power zones

2. **Medium Priority (Extended Analytics)**
   - hrTSS/TRIMP (for activities without power)
   - Efficiency Factor
   - Variability Index

3. **Lower Priority (Advanced)**
   - W'bal (requires CP/W' testing)
   - Aerobic Decoupling
   - Ramp Rate warnings

### Data Requirements

| Metric | Required Data |
|--------|---------------|
| NP | 1-second power samples |
| TSS | NP + FTP setting |
| hrTSS | HR samples + LTHR + HR_max + HR_rest |
| CTL/ATL | Daily TSS values |
| W'bal | Power samples + CP + W' |
| EF | NP + avg HR |
| Calories | Power OR (HR + weight + age) |

### User Settings Needed

- FTP (Functional Threshold Power)
- LTHR (Lactate Threshold Heart Rate)  
- HR_max (Maximum Heart Rate)
- HR_rest (Resting Heart Rate)
- Weight (for calorie calculations)
- Age (for HR estimates)
- Gender (for TRIMP/calorie calculations)
