# FIT File Training Metrics Reference

This document catalogs the training metrics available in Garmin FIT (Flexible and Interoperable Data Transfer) files, based on the official FIT SDK profile. All field names and message types are sourced directly from the FIT SDK via the `fitdecode` Python library, which implements the official Garmin FIT Protocol specification.

## Sources

- **Primary**: Garmin FIT SDK Profile (via `fitdecode.profile` module, which implements the official Garmin FIT Protocol specification)
- **Secondary**: `fit_tool` library message definitions
- **Protocol**: FIT Protocol version as implemented in fitdecode 0.11.0

---

## 1. Standard FIT File Fields (Per-Record Data)

The `record` message (message type 20) contains per-sample data points, typically recorded at 1Hz intervals.

### Core Sensor Data

| Field Name | Description | Units | Source |
|------------|-------------|-------|--------|
| `timestamp` | Record timestamp | FIT epoch (1989-12-31) | Device clock |
| `position_lat` | Latitude | Semicircles (convert: × 180/2^31 = degrees) | GPS |
| `position_long` | Longitude | Semicircles | GPS |
| `heart_rate` | Heart rate | bpm | HR strap/optical |
| `power` | Instantaneous power | Watts | Power meter |
| `cadence` | Cadence | rpm (cycling) or spm (running) | Cadence sensor |
| `speed` | Ground speed | m/s | GPS or speed sensor |
| `enhanced_speed` | High-resolution speed | m/s (0.001 resolution) | Newer devices |
| `altitude` | Elevation | Meters (0.2m resolution) | Barometer/GPS |
| `enhanced_altitude` | High-resolution elevation | Meters (0.001 resolution) | Newer devices |
| `temperature` | Ambient temperature | °C | Temperature sensor |
| `distance` | Cumulative distance | Meters | Computed from GPS/speed |

### GPS Quality

| Field Name | Description | Units |
|------------|-------------|-------|
| `gps_accuracy` | Horizontal position error | Meters |
| `grade` | Current gradient | Percent (%) |
| `vertical_speed` | Vertical velocity | m/s |

### Advanced Power Metrics

| Field Name | Description | Units |
|------------|-------------|-------|
| `accumulated_power` | Cumulative work | Watts (sum) |
| `left_right_balance` | Power balance L/R | Percent (bit field) |
| `left_torque_effectiveness` | Left pedal torque efficiency | Percent |
| `right_torque_effectiveness` | Right pedal torque efficiency | Percent |
| `left_pedal_smoothness` | Left pedal stroke smoothness | Percent |
| `right_pedal_smoothness` | Right pedal stroke smoothness | Percent |
| `combined_pedal_smoothness` | Combined pedal smoothness | Percent |
| `left_pco` | Left platform center offset | mm |
| `right_pco` | Right platform center offset | mm |
| `left_power_phase` | Left power phase angles | Degrees (start, end) |
| `left_power_phase_peak` | Left peak power phase | Degrees (start, end) |
| `right_power_phase` | Right power phase angles | Degrees |
| `right_power_phase_peak` | Right peak power phase | Degrees |

### Running Dynamics

| Field Name | Description | Units |
|------------|-------------|-------|
| `vertical_oscillation` | Vertical bounce | mm |
| `stance_time` | Ground contact time | ms |
| `stance_time_percent` | Ground contact as % of stride | Percent |
| `stance_time_balance` | L/R ground contact balance | Percent |
| `step_length` | Step length | mm |
| `vertical_ratio` | Vertical oscillation / step length | Percent |

### Muscle Oxygen (SmO2)

| Field Name | Description | Units |
|------------|-------------|-------|
| `total_hemoglobin_conc` | Total hemoglobin concentration | g/dL |
| `saturated_hemoglobin_percent` | Muscle oxygen saturation | Percent |

### E-Bike/Motor

| Field Name | Description | Units |
|------------|-------------|-------|
| `motor_power` | E-bike motor power | Watts |
| `battery_soc` | Battery state of charge | Percent |
| `ebike_assist_mode` | Assist mode | Enum |
| `ebike_assist_level_percent` | Assist level | Percent |

### Zone Tracking

| Field Name | Description | Notes |
|------------|-------------|-------|
| `zone` | Current zone number | Real-time zone tracking |

---

## 2. Session-Level Summaries

The `session` message (message type 18) contains activity-wide aggregates, computed by the device at activity end.

### Basic Summaries

| Field Name | Description | Units |
|------------|-------------|-------|
| `start_time` | Activity start time | FIT timestamp |
| `total_elapsed_time` | Total clock time | Seconds |
| `total_timer_time` | Active/moving time | Seconds |
| `total_moving_time` | Time while moving | Seconds |
| `total_distance` | Total distance | Meters |
| `total_calories` | Calories burned | kcal |
| `total_ascent` | Elevation gain | Meters |
| `total_descent` | Elevation loss | Meters |
| `total_work` | Total mechanical work | Joules (kJ = J/1000) |

### Averages and Maximums

| Field Name | Description | Units |
|------------|-------------|-------|
| `avg_speed` / `enhanced_avg_speed` | Average speed | m/s |
| `max_speed` / `enhanced_max_speed` | Maximum speed | m/s |
| `avg_heart_rate` | Average heart rate | bpm |
| `max_heart_rate` | Maximum heart rate | bpm |
| `min_heart_rate` | Minimum heart rate | bpm |
| `avg_cadence` | Average cadence | rpm |
| `max_cadence` | Maximum cadence | rpm |
| `avg_power` | Average power | Watts |
| `max_power` | Maximum power | Watts |
| `avg_temperature` | Average temperature | °C |
| `max_temperature` | Maximum temperature | °C |

### Derived/Computed Metrics (Device-Computed)

These fields are computed by the device using proprietary algorithms:

| Field Name | Description | Units | Requires |
|------------|-------------|-------|----------|
| `normalized_power` | Normalized Power (NP) | Watts | Power data |
| `training_stress_score` | Training Stress Score (TSS) | Dimensionless | FTP + Power |
| `intensity_factor` | Intensity Factor (IF) | Ratio | FTP + Power |
| `threshold_power` | FTP used for calculation | Watts | User setting |
| `total_training_effect` | Aerobic Training Effect | 0.0-5.0 scale | HR + algorithm |
| `total_anaerobic_training_effect` | Anaerobic Training Effect | 0.0-5.0 scale | HR/Power + algorithm |
| `training_load_peak` | Training Load Peak (EPOC) | Dimensionless | Firstbeat algorithm |

### Zone Time Arrays

| Field Name | Description | Units |
|------------|-------------|-------|
| `time_in_hr_zone` | Time spent in each HR zone | Seconds (array) |
| `time_in_power_zone` | Time spent in each power zone | Seconds (array) |
| `time_in_speed_zone` | Time spent in each speed zone | Seconds (array) |
| `time_in_cadence_zone` | Time spent in each cadence zone | Seconds (array) |

### Advanced Session Metrics

| Field Name | Description | Units |
|------------|-------------|-------|
| `avg_vam` | Average vertical ascent meters/hour | m/h |
| `avg_vertical_oscillation` | Avg running bounce | mm |
| `avg_stance_time` | Avg ground contact time | ms |
| `avg_step_length` | Average step length | mm |
| `avg_left_torque_effectiveness` | Avg L torque efficiency | % |
| `avg_right_torque_effectiveness` | Avg R torque efficiency | % |
| `avg_left_pedal_smoothness` | Avg L pedal smoothness | % |
| `avg_right_pedal_smoothness` | Avg R pedal smoothness | % |

### HRV Session Metrics (Newer Devices)

| Field Name | Description | Units |
|------------|-------------|-------|
| `sdrr_hrv` | SDRR (standard deviation of RR intervals) | ms |
| `rmssd_hrv` | RMSSD (root mean square of successive differences) | ms |
| `avg_stress` | Average stress level | 0-100 |

### Sport Classification

| Field Name | Description |
|------------|-------------|
| `sport` | Primary sport type (enum: cycling=2, running=1, etc.) |
| `sub_sport` | Sub-sport (road=7, trail=3, indoor_cycling=6, etc.) |

---

## 3. Lap-Level Data

The `lap` message (message type 19) contains per-lap aggregates with similar fields to session:

- Same avg/max fields as session
- `normalized_power` (per-lap NP)
- `time_in_hr_zone`, `time_in_power_zone` (per-lap)
- `intensity` - lap intensity level
- `lap_trigger` - what caused the lap (manual, distance, position, etc.)

---

## 4. Heart Rate and Power Zone Data

### Zone Configuration Messages

**`zones_target` message (type 7)** - Defines calculation method:

| Field Name | Description |
|------------|-------------|
| `max_heart_rate` | User's max HR setting |
| `threshold_heart_rate` | Lactate threshold HR (LTHR) |
| `functional_threshold_power` | FTP setting |
| `hr_calc_type` | How HR zones are calculated (custom, percent_max_hr, percent_lthr) |
| `pwr_calc_type` | How power zones are calculated (custom, percent_ftp) |

**`hr_zone` message (type 8)** - Individual HR zone boundaries:

| Field Name | Description |
|------------|-------------|
| `message_index` | Zone number (0-based) |
| `high_bpm` | Upper boundary of zone |
| `name` | Zone name (e.g., "Zone 1", "Recovery") |

**`power_zone` message (type 9)** - Individual power zone boundaries:

| Field Name | Description |
|------------|-------------|
| `message_index` | Zone number (0-based) |
| `high_value` | Upper boundary in Watts |
| `name` | Zone name (e.g., "Active Recovery", "Threshold") |

### Zone Presence in FIT Files

- **Garmin devices**: Include `zones_target`, `hr_zone`, and `power_zone` messages when user has configured zones
- **Third-party devices**: May or may not include zone definitions
- **Zone time arrays**: `time_in_hr_zone` and `time_in_power_zone` in session/lap messages are populated if zones are configured

---

## 5. Self-Contained vs External Context

### Self-Contained (No External Data Needed)

These can be computed from raw record data alone:

| Metric | Computation |
|--------|-------------|
| Total distance | Sum of `distance` deltas or GPS track length |
| Total time | `timestamp` span |
| Avg/Max HR, power, speed, cadence | Statistical aggregates |
| Elevation gain/loss | Sum positive/negative `altitude` deltas |
| Total work (kJ) | Integral of power × time |
| Avg VAM | Total ascent / climbing time × 3600 |

### Requires External Context

These metrics require user-specific thresholds not always in the FIT file:

| Metric | Required Context | Notes |
|--------|------------------|-------|
| **TSS** | FTP (Functional Threshold Power) | TSS = (seconds × NP × IF) / (FTP × 3600) × 100 |
| **IF** (Intensity Factor) | FTP | IF = NP / FTP |
| **NP** (Normalized Power) | None (algorithm only) | 30-second rolling avg, raised to 4th power, averaged, then 4th root |
| **HR Zone time** | Zone boundaries or Max HR/LTHR | Needs `zones_target` or external config |
| **Power Zone time** | Zone boundaries or FTP | Needs `power_zone` messages or FTP |
| **W' Balance** | W' (anaerobic capacity) + CP (critical power) | Never in FIT file - must be externally configured |
| **Training Effect** | Proprietary algorithm + VO2max estimate | Device computes, not reproducible |
| **Body Battery** | Proprietary (Firstbeat) | Not in activity FIT files |

### Zone Calculation Methods

When zones are defined as percentages:

**HR Zones (Coggan/Friel 5-zone model based on LTHR)**:
- Zone 1: < 81% LTHR (Active Recovery)
- Zone 2: 81-89% LTHR (Endurance)  
- Zone 3: 90-93% LTHR (Tempo)
- Zone 4: 94-99% LTHR (Threshold)
- Zone 5: 100-106% LTHR (VO2max)

**Power Zones (Coggan 7-zone model based on FTP)**:
- Zone 1: < 55% FTP (Active Recovery)
- Zone 2: 55-74% FTP (Endurance)
- Zone 3: 75-89% FTP (Tempo)
- Zone 4: 90-104% FTP (Threshold)
- Zone 5: 105-120% FTP (VO2max)
- Zone 6: 121-150% FTP (Anaerobic)
- Zone 7: > 150% FTP (Neuromuscular)

---

## 6. HRV Data

The `hrv` message (type 78) contains beat-to-beat interval data:

| Field Name | Description |
|------------|-------------|
| `time` | Array of RR intervals (time between heartbeats) in ms |

HRV data enables computation of:
- RMSSD (root mean square of successive differences)
- SDNN (standard deviation of NN intervals)
- pNN50 (percentage of successive intervals differing by >50ms)
- Frequency domain analysis (LF/HF ratio)

---

## 7. Device and File Metadata

### `file_id` message (type 0)

| Field Name | Description |
|------------|-------------|
| `type` | File type (4 = activity) |
| `manufacturer` | Device manufacturer ID |
| `product` | Product ID |
| `serial_number` | Device serial |
| `time_created` | File creation timestamp |

### `device_info` message (type 23)

| Field Name | Description |
|------------|-------------|
| `device_index` | Device slot (0 = primary) |
| `device_type` | Type (HR monitor, power meter, etc.) |
| `manufacturer` | Sensor manufacturer |
| `product` | Sensor product ID |
| `serial_number` | Sensor serial |
| `software_version` | Firmware version |
| `battery_status` | Battery level |

### `user_profile` message (type 3)

| Field Name | Description |
|------------|-------------|
| `weight` | User weight (kg) |
| `height` | User height (cm) |
| `age` | User age |
| `gender` | User gender |
| `resting_heart_rate` | Resting HR |
| `default_max_heart_rate` | Max HR setting |
| `activity_class` | Fitness level (0-100) |

---

## 8. Event Markers

The `event` message (type 21) records discrete events:

| Event Type | Description |
|------------|-------------|
| `timer` (0) | Start/stop/pause |
| `workout` (3) | Workout start/end |
| `workout_step` (4) | Workout interval change |
| `lap` (9) | Lap marker |
| `hr_high_alert` (13) | HR above threshold |
| `hr_low_alert` (14) | HR below threshold |
| `power_high_alert` (19) | Power above threshold |
| `power_low_alert` (20) | Power below threshold |
| `recovery_hr` (21) | Recovery HR measurement |
| `front_gear_change` (42) | Front derailleur shift |
| `rear_gear_change` (43) | Rear derailleur shift |
| `calibration` (36) | Power meter calibration |

---

## 9. Workout Structure

### `workout` message (type 26)

| Field Name | Description |
|------------|-------------|
| `workout_name` | Workout title |
| `num_valid_steps` | Number of intervals |
| `sport` | Target sport |

### `workout_step` message (type 27)

| Field Name | Description |
|------------|-------------|
| `duration_type` | How step ends (time, distance, calories, HR, power, etc.) |
| `duration_value` | Duration target |
| `target_type` | Target metric (HR, power, cadence, speed) |
| `target_hr_zone` | Target HR zone number |
| `target_power_zone` | Target power zone number |
| `custom_target_power_low/high` | Custom power range |
| `custom_target_heart_rate_low/high` | Custom HR range |
| `intensity` | Step intensity (active, rest, warmup, cooldown) |

---

## 10. Derived Metric Formulas

### Normalized Power (NP)

```
1. Calculate 30-second rolling average of power
2. Raise each value to 4th power
3. Take mean of these values
4. Take 4th root of the result

NP = (mean(rolling_30s_power^4))^0.25
```

### Intensity Factor (IF)

```
IF = NP / FTP
```

### Training Stress Score (TSS)

```
TSS = (duration_seconds × NP × IF) / (FTP × 3600) × 100

Or equivalently:
TSS = (duration_seconds × NP^2) / (FTP^2 × 36)
```

### W' Balance (Skiba model)

```
For each sample i:
  if power[i] > CP:
    W'_bal[i] = W'_bal[i-1] - (power[i] - CP) × dt
  else:
    W'_bal[i] = W' - (W' - W'_bal[i-1]) × e^(-dt × (CP - power[i]) / W')

Where:
  W' = anaerobic work capacity (typically 15-25 kJ)
  CP = critical power (similar to FTP)
  dt = time step (seconds)
```

### Variability Index (VI)

```
VI = NP / Average Power
```

### Efficiency Factor (EF)

```
EF = NP / Avg Heart Rate
```

---

## 11. Sport Types Reference

Common `sport` enum values:

| Value | Sport |
|-------|-------|
| 0 | Generic |
| 1 | Running |
| 2 | Cycling |
| 4 | Fitness Equipment |
| 5 | Swimming |
| 11 | Walking |
| 17 | Hiking |
| 21 | E-Biking |

Common `sub_sport` values:

| Value | Sub-Sport |
|-------|-----------|
| 1 | Treadmill |
| 5 | Spin |
| 6 | Indoor Cycling |
| 7 | Road (cycling) |
| 8 | Mountain (cycling) |
| 14 | Indoor Rowing |
| 45 | Indoor Running |
| 46 | Gravel Cycling |

---

## Implementation Notes for Training Dashboard

1. **Ingest all standard record fields**: The current `ingest.py` captures the basics but misses running dynamics, pedal metrics, and SmO2 data.

2. **Store zone definitions**: When present, extract and store `zones_target`, `hr_zone`, and `power_zone` messages to enable zone-based analysis without requiring user to re-enter settings.

3. **Preserve session-computed metrics**: TSS, IF, NP, and Training Effect from the FIT file are device-authoritative. Store them even if you plan to recompute.

4. **Handle user context gracefully**: 
   - If FTP is in `zones_target.functional_threshold_power`, use it
   - Otherwise, require user to set FTP in the app
   - Same for LTHR and max HR

5. **W' Balance requires external config**: W' and CP are never in FIT files. These must come from user profile or be estimated from power curve analysis.

6. **HRV for recovery metrics**: The `hrv` message enables stress/recovery analysis but requires significant post-processing.

7. **Time-in-zone is pre-computed**: `time_in_hr_zone` and `time_in_power_zone` arrays are in session/lap messages when the device computed them. Use these when available rather than recomputing.
