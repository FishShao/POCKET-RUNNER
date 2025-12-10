import time
import board
import busio
import displayio
import terminalio
import digitalio
import neopixel
import adafruit_adxl34x
from adafruit_display_text import label
import i2cdisplaybus
import adafruit_displayio_ssd1306
import vectorio
import random
import microcontroller

from rotary_encoder import RotaryEncoder

print("Starting Pocket Runner Final V9 (High Score)...")

displayio.release_displays()

#  Initialize OLED Display
try:
    i2c = busio.I2C(board.SCL, board.SDA)
except Exception as e:
    print("I2C Error:", e)

try:
    display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
    WIDTH = 128
    HEIGHT = 64
    display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT)
except Exception as e:
    print("OLED Error:", e)

#  Initialize Accelerometer (ADXL345)
try:
    accel = adafruit_adxl34x.ADXL345(i2c)
except Exception as e:
    print("ADXL Error:", e)

#  Initialize Rotary Encoder
encoder = RotaryEncoder(board.A2, board.A3, debounce_ms=3, pulses_per_detent=3)
last_encoder_pos = 0

#  Initialize Button
btn = digitalio.DigitalInOut(board.MISO) 
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP 

#  Initialize NeoPixel for status LED
pixel = neopixel.NeoPixel(board.MOSI, 1)
pixel.brightness = 0.2
pixel.fill((0, 0, 0))

# Common Colors
WHITE = 0xFFFFFF
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (180, 0, 255)
OFF = (0, 0, 0)

# ===========================================================
# Boot Animation
# ===========================================================
def play_boot_animation():
    """
    Draws a simple boot-up animation:
    - Shows text "SYSTEM BOOT..."
    - Draws a small runner sliding across the screen
    """
    boot_group = displayio.Group()
    loading_text = label.Label(terminalio.FONT, text="SYSTEM BOOT...", color=WHITE, x=25, y=20)
    boot_group.append(loading_text)
    
    # Create the runner graphic
    runner_group = displayio.Group()
    palette = displayio.Palette(1)
    palette[0] = WHITE
    # Head (Circle)
    head = vectorio.Circle(pixel_shader=palette, radius=3, x=0, y=0)
    # Body (Triangle)    
    body_points = [(-3, 3), (3, 3), (0, 10)]
    body = vectorio.Polygon(pixel_shader=palette, points=body_points, x=0, y=0)
    runner_group.append(head)
    runner_group.append(body)
    
    # Initial position
    runner_group.x = -10
    runner_group.y = 45
    boot_group.append(runner_group)
    
    # Show on screen
    display.root_group = boot_group
    
    # Animate movement
    for x in range(-10, 138, 4):
        runner_group.x = x
        # Small bounce effect
        if (x // 4) % 2 == 0: runner_group.y = 42
        else: runner_group.y = 45
        time.sleep(0.03)

# Play the animation once at startup
play_boot_animation()

# =========================================
# High Score Handler (stored in microcontroller.nvm)
# =========================================
class HighScoreHandler:
    """
    Handles reading and writing high scores to the microcontroller's
    Non-Volatile Memory (NVM) so scores persist after power off.
    """
    def __init__(self):
        # 5 bytes per entry, 2 score + 3 name, 3 entries allowed
        self.entry_size = 5       # bytes per high-score entry
        self.total_entries = 3    # 3 stored scores
        
        # Check if NVM is empty (0xFF), if so, reset to defaults
        if microcontroller.nvm[0] == 255: self.reset_nvm()

    def reset_nvm(self):
        """Resets NVM to default values (Score: 0, Name: AAA)"""
        default_data = []
        for _ in range(self.total_entries):
            # 0, 0 = Score 0; 65 = 'A'
            default_data.extend([0, 0, ord('A'), ord('A'), ord('A')])
        for i in range(len(default_data)):
            microcontroller.nvm[i] = default_data[i]

    def get_scores(self):
        """Reads scores from NVM and returns a list of dictionaries."""
        scores = []
        for i in range(self.total_entries):
            start = i * self.entry_size
            # Reconstruct 16-bit score from 2 bytes
            score = (microcontroller.nvm[start] << 8) | microcontroller.nvm[start+1]
            # Reconstruct name from 3 bytes
            name = ""
            for j in range(3): name += chr(microcontroller.nvm[start + 2 + j])
            scores.append({'score': score, 'name': name})
        return scores

    def is_high_score(self, new_score):
        """Checks if the new score is higher than the lowest saved score."""
        scores = self.get_scores()
        return new_score > scores[-1]['score']

    def save_score(self, new_score, new_name):
        """Saves a new high score, sorts the list, and writes back to NVM."""
        scores = self.get_scores()
        scores.append({'score': new_score, 'name': new_name})
        # Sort by score descending
        scores.sort(key=lambda x: x['score'], reverse=True)
        # Keep only top 3
        scores = scores[:3]
        # Write to memory
        for i, entry in enumerate(scores):
            start = i * self.entry_size
            microcontroller.nvm[start] = (entry['score'] >> 8) & 0xFF # High byte
            microcontroller.nvm[start+1] = entry['score'] & 0xFF # Low byte
            for j in range(3): microcontroller.nvm[start + 2 + j] = ord(entry['name'][j])

# =========================================
# 2. Sensor Logic (Filtering)
# =========================================
class MotionSensor:
    def __init__(self, sensor):
        self.sensor = sensor
        self.alpha = 0.1        # Smoothing factor for filter
        
    def update(self):
        """Returns the raw X, Y, Z acceleration values."""
        if self.sensor is None: return 0, 0, 9.8
        try:
            x, y, z = self.sensor.acceleration
            return x, y, z
        except Exception:
            return 0, 0, 9.8

    def check_double_tap(self):
        if self.sensor is None: return False
        return self.sensor.events["tap"]

# =========================================
# 3. Game Logic Class
# =========================================
class PocketRunner:
    def __init__(self):
        # Y-coordinates for the 3 lanes
        self.lane_coords = [12, 32, 52] 
        self.current_lane_index = 1 
        
        # Game State Variables
        self.score = 0
        self.level = 1
        self.speed = 3
        self.difficulty = "Easy"
        
        # Obstacle Spawning Rhythm
        self.spawn_timer = 0
        self.min_spawn_gap = 20
        self.max_spawn_gap = 40
        self.spawn_rate = 0
        
        # Player Position
        self.player_x = 10.0
        
        # Time Management
        self.level_duration = 5
        self.level_start_time = 0
        self.time_left = 5
        self.game_start_time = 0 # Global start time
        
        # LED Timers
        self.coin_flash_timer = 0 
        self.level_flash_timer = 0
        self.coins_spawned_this_level = 0
        
        # Entities
        self.obstacles = [] 
        self.coins = []     
        
        # Graphics Group
        self.game_group = displayio.Group()
        
        # Create Player (Triangle Shape)
        palette = displayio.Palette(1)
        palette[0] = WHITE
        triangle_points = [(0, 0), (0, 12), (8, 6)]  # Narrow triangle
        self.player_shape = vectorio.Polygon(pixel_shader=palette, points=triangle_points, x=0, y=0)
        
        self.update_player_pos()
        self.game_group.append(self.player_shape)
        
        # UI Labels (Score, Level, Time)
        self.score_label = label.Label(terminalio.FONT, text="Score:0", color=WHITE, x=0, y=5)
        self.level_label = label.Label(terminalio.FONT, text="Lv:1", color=WHITE, x=50, y=5)
        self.time_label = label.Label(terminalio.FONT, text="T:50", color=WHITE, x=90, y=5)
        
        self.game_group.append(self.score_label)
        self.game_group.append(self.level_label)
        self.game_group.append(self.time_label)

    def set_difficulty(self, mode):
        """Sets parameters based on selected difficulty."""
        self.difficulty = mode
        if mode == "Easy":
            self.speed = 2
            self.min_spawn_gap = 40
            self.max_spawn_gap = 70 
        elif mode == "Medium":
            self.speed = 3
            self.min_spawn_gap = 25
            self.max_spawn_gap = 50
        elif mode == "Hard":
            self.speed = 5
            self.min_spawn_gap = 15
            self.max_spawn_gap = 30
            
    def spawn_entity(self):
        """Handles spawning of Obstacles and Coins."""
        # Rhythm check
        if self.spawn_timer > 0:
            self.spawn_timer -= 1
            return 

        # Prevent clogging, don't spawn if too many obstacles on right side
        recent_obstacles_count = 0
        for obs in self.obstacles:
            if obs["x"] > 100: recent_obstacles_count += 1
        if recent_obstacles_count >= 2:
            self.spawn_timer = 5
            return

        # 1. ALWAYS spawn an Obstacle
        obs_lane_idx = random.randint(0, 2) 
        obs_y = self.lane_coords[obs_lane_idx]
        palette = displayio.Palette(1)
        palette[0] = WHITE
        
        shape = vectorio.Rectangle(pixel_shader=palette, width=10, height=10, x=130, y=obs_y-5)
        self.obstacles.append({"shape": shape, "x": 130, "y": obs_y})
        self.game_group.append(shape)

        # 2. Try to spawn a Coin: max 2 per 5-sec interval
        if self.coins_spawned_this_level < 2:
            # Find a lane that is NOT occupied by the obstacle
            available_lanes = [0, 1, 2]
            available_lanes.remove(obs_lane_idx)
            
            coin_lane_idx = random.choice(available_lanes)
            coin_y = self.lane_coords[coin_lane_idx]
            
            c_shape = vectorio.Circle(pixel_shader=palette, radius=4, x=130, y=coin_y)
            self.coins.append({"shape": c_shape, "x": 130, "y": coin_y})
            self.game_group.append(c_shape)
            
            self.coins_spawned_this_level += 1 # Increment counter
        # Reset timer for next spawn
        self.spawn_timer = random.randint(self.min_spawn_gap, self.max_spawn_gap)

    def reset_game(self):
        """Resets all game variables for a new session."""
        self.score = 0
        self.level = 1
        self.player_x = 10.0
        self.obstacles.clear()
        self.coins.clear()
        # Remove entities from display group, keep UI
        while len(self.game_group) > 4: self.game_group.pop()
        self.set_difficulty(self.difficulty)
        self.current_lane_index = 1
        self.update_player_pos()
        # Record global start time
        self.game_start_time = time.monotonic()
        

    def update_player_pos(self):
        """Updates player visual position."""
        # Constrain X position
        if self.player_x < 0: self.player_x = 0
        if self.player_x > 115: self.player_x = 115
        self.player_shape.x = int(self.player_x)
        self.player_shape.y = self.lane_coords[self.current_lane_index] - 6

    def check_collision(self):
        """Checks collisions between Player and Obstacles/Coins."""
        player_x = self.player_shape.x + 4
        player_y = self.player_shape.y + 6
        
        # Check Coins
        for coin in self.coins[:]:
            if abs(coin["x"] - player_x) < 15 and abs(coin["y"] - player_y) < 10:
                self.coins.remove(coin)
                self.game_group.remove(coin["shape"])
                self.score += 1
                self.coin_flash_timer = 10    # Trigger Green LED
        # Check Obstacles        
        for obs in self.obstacles[:]:
            if abs(obs["x"] - player_x) < 12 and abs(obs["y"] - player_y) < 10:
                return True     # Collision detected
        return False


# Screen Drawing Helpers
    def draw_title_screen(self):
        group = displayio.Group()
        title = label.Label(terminalio.FONT, text="POCKET RUNNER", scale=1, x=25, y=20, color=WHITE)
        sub = label.Label(terminalio.FONT, text=">>> PLAY <<<", x=25, y=45, color=WHITE)
        group.append(title)
        group.append(sub)
        display.root_group = group

    def draw_menu(self, idx):
        group = displayio.Group()
        title = label.Label(terminalio.FONT, text="DIFFICULTY", scale=1, x=35, y=10, color=WHITE)
        group.append(title)
        opts = ["Easy", "Medium", "Hard"]
        for i, opt in enumerate(opts):
            prefix = "> " if i == idx else "  "
            lbl = label.Label(terminalio.FONT, text=prefix + opt, x=30, y=30 + (i*12), color=WHITE)
            group.append(lbl)
        display.root_group = group 

    def draw_end_screen(self, title_text, color):
        group = displayio.Group()
        pixel.fill(color)
        t = label.Label(terminalio.FONT, text=title_text, scale=2, x=10, y=20, color=WHITE)
        s = label.Label(terminalio.FONT, text=f"Score: {self.score}", x=45, y=45, color=WHITE)
        r = label.Label(terminalio.FONT, text="CONTINUE", x=45, y=58, color=WHITE)
        group.append(t)
        group.append(s)
        group.append(r)
        display.root_group = group

    def draw_input_screen(self, char_index, current_chars):
        group = displayio.Group()
        title = label.Label(terminalio.FONT, text="NEW HIGH SCORE!", color=WHITE, x=20, y=10)
        display_text = ""
        for i in range(3):
            if i == char_index: display_text += f"[{current_chars[i]}] "
            else: display_text += f" {current_chars[i]}  "
        chars_lbl = label.Label(terminalio.FONT, text=display_text, scale=1, x=25, y=35, color=WHITE)
        group.append(title)
        group.append(chars_lbl)
        display.root_group = group

    def draw_highscore_board(self, scores_list):
        group = displayio.Group()
        title = label.Label(terminalio.FONT, text="TOP SCORES", scale=1, x=35, y=5, color=WHITE)
        group.append(title)
        for i, entry in enumerate(scores_list):
            y_pos = 20 + (i * 15)
            text = f"{i+1}. {entry['name']}   {entry['score']}"
            lbl = label.Label(terminalio.FONT, text=text, x=20, y=y_pos, color=WHITE)
            group.append(lbl)
        display.root_group = group

# =========================================
# 4. Main Loop
# =========================================

game = PocketRunner()
motion = MotionSensor(accel)
hs_handler = HighScoreHandler()

state = "TITLE" 
diff_options = ["Easy", "Medium", "Hard"]
diff_idx = 0
last_pos = 0

input_chars = ['A', 'A', 'A']
char_idx = 0 
alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
alpha_idx = 0

print("Loop Starting...")
game.draw_title_screen() 

while True:
    # Update sensors
    encoder_changed = encoder.update()
    current_pos = encoder.position
    acc_x, acc_y, acc_z = motion.update()
    
    # ---------------- TITLE ----------------
    if state == "TITLE":
        pixel.fill(OFF) 
        if not btn.value:      # Button pressed
            state = "MENU"
            game.draw_menu(diff_idx) 
            time.sleep(0.5) 

    # ---------------- MENU STATE ----------------
    elif state == "MENU":
        pixel.fill(OFF)
        # Handle Rotary Encoder selection
        if encoder_changed:
            if current_pos > last_pos: diff_idx = (diff_idx + 1) % 3 
            elif current_pos < last_pos: diff_idx = (diff_idx - 1) % 3 
            last_pos = current_pos
            game.draw_menu(diff_idx)
        
        # Confirm selection
        if not btn.value:
            game.set_difficulty(diff_options[diff_idx])
            game.reset_game()
            display.root_group = game.game_group
            state = "PLAY"
            time.sleep(0.5)

    # ---------------- PLAY STATE ----------------
    elif state == "PLAY":
        # 1. Tilt Y-Axis -> Lane Selection
        if acc_y < -3.0:      
            game.current_lane_index = 0 
        elif acc_y > 3.0:     
            game.current_lane_index = 2 
        else:                 
            game.current_lane_index = 1 
        
        # 2. Tilt X-Axis -> Left/Right Movement (With Deadzone)
        if abs(acc_x) > 3.0: 
            game.player_x -= acc_x * 1.0    # Sensitivity

        # 3. Global Time Calculation (Total 50s)
        total_elapsed = time.monotonic() - game.game_start_time
        game.time_left = int(50 - total_elapsed)
        
        # 4. Auto Level Up (Every 5 seconds)
        current_stage = int(total_elapsed // 5) + 1

        if current_stage > game.level:
            game.level = current_stage
            game.coins_spawned_this_level = 0 # Reset coin limit for new level
            
            # Debug info
            print(f"Level Up! {game.level} Gap: {game.min_spawn_gap}")
            
            # Make obstacles denser
            if game.min_spawn_gap > 10: game.min_spawn_gap -= 2
            if game.max_spawn_gap > 15: game.max_spawn_gap -= 4
            
            # Trigger Yellow LED for level up
            game.level_flash_timer = 20
            
            # Win Condition
            if game.level > 10: state = "WIN"

        # LED Logic - Green for Coin > Yellow for Level Up > Off
        if game.coin_flash_timer > 0:
            pixel.fill(GREEN) 
            game.coin_flash_timer -= 1
        elif game.level_flash_timer > 0:
            pixel.fill(YELLOW)
            game.level_flash_timer -= 1
        else:
            pixel.fill(OFF)

        # 5. Update Game Entities
        game.update_player_pos()
        game.spawn_entity()
        
        # Move objects to the left
        for entity in game.obstacles + game.coins:
            entity["x"] -= game.speed 
            entity["shape"].x = int(entity["x"])
            
            # Remove objects that go off-screen
            if entity["x"] < -10:
                if entity in game.obstacles:
                    game.obstacles.remove(entity)
                    game.game_group.remove(entity["shape"])
                elif entity in game.coins:
                    game.coins.remove(entity)
                    game.game_group.remove(entity["shape"])
        
        # Check Collision
        if game.check_collision(): state = "GAMEOVER"
        
        # Check Win by Time
        if game.time_left <= 0: state = "WIN"

        # Update UI Text
        game.score_label.text = f"Score:{game.score}"
        game.level_label.text = f"Lv:{game.level}"
        game.time_label.text  = f"T:{game.time_left}"
        
        # Frame delay
        time.sleep(0.04)


    # ---------------- GAME OVER / WIN ----------------
    elif state == "GAMEOVER" or state == "WIN":
        if state == "GAMEOVER": game.draw_end_screen("GAME OVER", RED)
        else: game.draw_end_screen("YOU WIN!", PURPLE)
        
        if not btn.value:
            pixel.fill(OFF)
            time.sleep(0.5)
            # Check High Score
            if hs_handler.is_high_score(game.score):
                state = "INPUT_NAME"
                input_chars = ['A', 'A', 'A']
                char_idx = 0
                alpha_idx = 0
                game.draw_input_screen(char_idx, input_chars)
            else:
                state = "SHOW_HIGHSCORE"
                scores = hs_handler.get_scores()
                game.draw_highscore_board(scores)

    # ---------------- INPUT HIGH SCORE NAME ----------------
    elif state == "INPUT_NAME":
        # Select Character using Encoder
        if encoder_changed:
            if current_pos > last_pos: alpha_idx = (alpha_idx + 1) % 26
            elif current_pos < last_pos: alpha_idx = (alpha_idx - 1) % 26
            last_pos = current_pos
            input_chars[char_idx] = alphabet[alpha_idx]
            game.draw_input_screen(char_idx, input_chars)
        
        # Confirm Character using Button
        if not btn.value:
            char_idx += 1
            time.sleep(0.3) 
            if char_idx < 3:
                alpha_idx = 0 
                game.draw_input_screen(char_idx, input_chars)
            else:
                # Save and show board
                final_name = "".join(input_chars)
                hs_handler.save_score(game.score, final_name)
                state = "SHOW_HIGHSCORE"
                scores = hs_handler.get_scores()
                game.draw_highscore_board(scores)

    # ---------------- SHOW HIGH SCORE BOARD ----------------
    elif state == "SHOW_HIGHSCORE":
        if not btn.value:
            state = "TITLE"
            game.draw_title_screen()
            time.sleep(0.5)

