# POCKET-RUNNER

## Overview
Pocket Runner is a fast-paced handheld electronic game inspired by 90s toys like Bop It and Brain Warp.

Players control a small runner character by tilting, shifting lanes, avoiding obstacles, and collecting coins, all under a strict time limit.

The device features:
- SSD1306 OLED display
- ADXL345 accelerometer (for lane switching + left/right movement)
- Rotary encoder (for menus + name input)
- NeoPixel LED feedback
- Game Over / Win screens
- High Score saving to ESP32-C3 NVM
- Animated boot splash
- Custom 3D-printed enclosure

## How to Play
1. Turn on the device

    The animated boot screen plays once at startup.

2. Select difficulty

    Rotate encoder to choose:
    - Easy
    - Medium
    - Hard
    
    Press button to confirm.

3. During the game
    - Tilt device forward/back to switch lanes (3-lane runner)
    - Tilt left/right to move horizontally
    - Avoid oncoming obstacles
    - Collect coins to increase score
    - Survive 50 seconds to win the game

4. End Conditions
    - Collision → ***GAME OVER***
    - Time reaches zero → ***YOU WIN***

5. High Score Entry
    
    If your score is in the top 3, rotate the encoder to select initials and save to the list.

6. Restart
    
    Press the button to restart without power cycling.

## Game Features
### Core Gameplay
- Smooth 3-lane runner mechanic
- Obstacle spawning with dynamic spacing
- Coin collection system
- Automatic level-up every 5 seconds (up to Level 10)

### Difficulty Settings
Each mode adjusts:
- Player speed
- Obstacle spawn frequency
- Game pacing

### Sensors + Input
ADXL345 for:
- Lane switches (Y-axis tilt)
- Left/right position (X-axis tilt)

Rotary encoder
- Menu navigation
- High score name selection

### Display & UI
- Boot animation with bouncing runner
- Title screen
- Menu screen
- Real-time HUD:
    - Score
    - Level
    - Time Left
- Game Over / Win screens
- High Score leaderboard

### NeoPixel LED
- Green flash = coin collected
- Yellow flash = level up
- Red = Game Over
- Off = normal gameplay

### High Score System
Stored in microcontroller.nvm (persistent memory):
- Top 3 scores
- 3-character initials
- Automatic sorting

## Code Structure
```
main.py                  # Game logic, animation, input handling, rendering
rotary_encoder.py        # Rotary encoder driver
/lib                     # CircuitPython libraries
assets/                  # Optional graphics (if any)
```

## Game Mechanics
Pocket Runner combines lane-based movement, tilt-controlled positioning, and dynamic obstacle generation to create a fast reaction-based gameplay loop. The core mechanics include:

1. Three-Lane Movement

    The player occupies one of three fixed lanes. Tilting the device forward moves the character to another lane. This allows quick, intuitive lane switching using the ADXL345’s Y-axis.

2. Horizontal Position Control

    In addition to lane switching, the player can shift horizontally Tilting left/right (X-axis) moves the runner smoothly across the lane. Used to fine-tune the position to avoid tighter obstacles

3. Obstacle & Coin Spawning

    The game continuously spawns:
    - **Obstacles** (rectangles) in random lanes
    - **Coins** (circles) in the remaining lanes

    Spawn timing is controlled by:
    - Difficulty setting
    - A minimum/maximum gap
    - Anti-clogging logic that prevents unfair overlaps
    Only two coins may spawn per level interval.

4. Collision & Scoring
    - Touching a coin → +1 score
    - Touching an obstacle → immediate Game Over
    - Collision is checked using bounding-box proximity
    Score also influences high-score ranking stored in NVM.

5. Level Progression

    The full game lasts 50 seconds. Every 5 seconds, the game levels up automatically:
    - Obstacle spawn rate increases
    - Coin limit resets
    - NeoPixel flashes yellow
    - Up to Level 10 (after which the player wins)
    This creates a rising difficulty curve that becomes denser and more intense.

6. Win & Loss Condition

    **You Win** if:
    
    The timer reaches zero without a collision

    **Game Over** if:

    Player collides with any obstacle

    After either condition, the player can restart instantly without rebooting.

## Enclosure Design
The enclosure is inspired by the ergonomic form of classic game controllers, providing a comfortable handheld grip during gameplay. Curved edges and natural resting zones for the fingers make the device easy to hold while tilting, shaking, and rotating the unit.

Internally, the enclosure was designed with a service-friendly layout:
- All electronic components except the LiPo battery are either snap-fit into dedicated slots or secured using screws, ensuring a stable and reliable internal structure. All major components, including the rotary encoder, OLED display, NeoPixel, and power switch, which fit into precisely dimensioned snap-in pockets or dedicated screw posts, preventing internal movement and maintaining alignment with external openings.
- The perfboard is held in place using a hybrid system of snap-fit brackets and screw mounts, ensuring it stays completely rigid during motion-based gameplay while still being removable for inspection or rework.
- The OLED screen, rotary encoder, and on/off switch each have precisely sized cutouts and mounting bosses to ensure proper alignment with the outer shell.
- A removable lid allows easy access to the electronics without disassembling the entire enclosure.
- A USB-C port opening is integrated into the side of shell so the device can be powered or programmed without opening the case.


