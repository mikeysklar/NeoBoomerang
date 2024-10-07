import board
import busio
import time
from adafruit_seesaw.seesaw import Seesaw
from adafruit_seesaw import rotaryio, digitalio
from adafruit_neokey.neokey1x4 import NeoKey1x4
from adafruit_hid.keycode import Keycode as K
from adafruit_hid.keycode import Keycode  # Add this if you haven't already
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.mouse import Mouse  # Import Mouse class
import usb_hid

# Setup I2C and NeoKeys
i2c = busio.I2C(board.SCL, board.SDA)
neokey1 = NeoKey1x4(i2c, addr=0x30)  # First NeoKey at 0x30
neokey2 = NeoKey1x4(i2c, addr=0x38)  # Second NeoKey at 0x38

# Initialize HID keyboard and mouse
kbd = Keyboard(usb_hid.devices)
mouse = Mouse(usb_hid.devices)  # Initialize mouse instance

# Setup seesaw for encoder (example for a QT Rotary Encoder)
encoder = Seesaw(i2c, addr=0x36)  # Adjust I2C address as needed
encoder_pos = rotaryio.IncrementalEncoder(encoder)
last_position = encoder_pos.position

# Setup button on pin 24 with internal pull-up
encoder.pin_mode(24, encoder.INPUT_PULLUP)
button = digitalio.DigitalIO(encoder, 24)

# Variables for handling button press and toggle
button_held = False
toggle_state = False  # Track the state for neo_init() and neo_off()

# Track the current state of pressed keys
pressed_keys = [False] * 8      # 4 keys from each NeoKey
this_time = 0
last_time = 0
debounce_duration = 0.01
pending_combo = None
last_combo_time = 0
combo_time_window = 0.01  # Time window for combo detection (in seconds)
cooldown_time = 0.01  # Increased cooldown time to prevent accidental repeats (in seconds)
minimum_hold_time = 0.01  # Minimum time keys must be held to register a chord (in seconds)
last_hold_time = 0
release_time_window = 0.01  # Time window to ensure all keys are released before new detection (in seconds)
last_release_time = 0

# Key Colors
uv_color = (128, 0, 255)        # UV
blue_color = (0, 0, 255)        # Blue
green_color = (0, 255, 0)       # Green
yellow_color = (255, 255, 0)    # Yellow
white_color = (255, 255, 255)   # White
red_color = (255, 0, 0)         # Red 
off_color = (0, 0, 0)         # OFF

# Define chord mappings
# Boomerang layout
#
#         E
#      0     7
#     1       6
#    2         5
#   3           4
#
chords = {
    (0,): K.E, (1,): K.I, (2,): K.A, (3,): K.S, (4,): K.SPACE,

    (0, 1): K.R, (0, 2): K.O, (0, 3): K.C, (1, 2): K.N, 
    (1, 3): K.L, (2, 3): K.T, (0, 5): K.M, (1, 5): K.G, 
    (2, 5): K.H, (3, 5): K.B, (0, 4): K.SPACE,

    (0, 1, 5): K.Y, (0, 2, 5): K.W, (0, 3, 5): K.X,
    (1, 2, 5): K.F, (1, 3, 5): K.K, (2, 3, 5): K.V,
    (0, 1, 2): K.D, (1, 2, 3): K.P, 

    (0, 1, 2, 5): K.J, (1, 2, 3, 5): K.Z,

    (0, 1, 2, 3): K.U,
    (0, 1, 2, 3, 5): K.Q,

    (0, 6): K.ONE, (1, 6): K.TWO,
    (2, 6): K.THREE, (3, 6): K.FOUR,

    (0, 1, 6): K.FIVE, (1, 2, 6): K.SIX,
    (2, 3, 6): K.SEVEN, (0, 2, 6): K.EIGHT,
    (1, 3, 6): K.NINE, 
    (0, 3, 6): K.UP_ARROW, 

    (0, 1, 2, 6): K.ZERO, (0, 1, 3, 6): K.RIGHT_ARROW, 
    (0, 2, 3, 6): K.LEFT_ARROW, (1, 2, 3, 6): K.ESCAPE,

    (0, 1, 2, 3, 6): K.DOWN_ARROW,

    (7,): K.BACKSPACE,

    (1, 4): K.TAB, (2, 4): K.PERIOD, (3, 4): K.MINUS,

    (0, 2, 3): K.SPACE, (0, 1, 3): K.BACKSPACE, 
    (2, 3, 4): K.FORWARD_SLASH, (0, 1, 4): K.ENTER, 
    (0, 2, 4): K.COMMA, (0, 2, 4): K.EQUALS, 
    (1, 3, 4): K.LEFT_BRACKET, (0, 3, 4): K.RIGHT_BRACKET, 
    (2, 3, 4): K.BACKSLASH, (1, 2, 4): K.BACKSPACE, 

    (0, 1, 3, 4): K.QUOTE, (0, 2, 3, 4): K.SEMICOLON,

    (0, 1, 2, 3, 4): K.GRAVE_ACCENT, 

}


# Function to initialize NeoKeys
def neo_init():
    # Initialize all pixels on NeoKey1 to UV
    for i in range(4):  # Assuming 4 pixels per NeoKey
        neokey1.pixels[i] = uv_color

    # Initialize all pixels on NeoKey2
    neokey2.pixels[0] = blue_color      # Blue
    neokey2.pixels[1] = green_color     # Green
    neokey2.pixels[2] = yellow_color    # Yellow
    neokey2.pixels[3] = red_color       # Red

def neo_off():
    # Initialize all pixels on NeoKey1 to UV
    for i in range(4):  # Assuming 4 pixels per NeoKey
        neokey1.pixels[i] = off_color
        neokey2.pixels[i] = off_color

# Function to check key combinations
def check_chords():
    global pending_combo, last_combo_time, last_hold_time, last_release_time
    current_combo = tuple(i for i, pressed in enumerate(pressed_keys) if pressed)
    current_time = time.monotonic()

    if current_combo:
        # Check if the keys are held for the minimum required time
        if last_hold_time == 0:
            last_hold_time = current_time

        if (current_time - last_hold_time) >= minimum_hold_time:
            if current_combo in chords:
                # Ensure keys are pressed within a short time window
                if pending_combo is None or (current_time - last_combo_time) <= combo_time_window:
                    if pending_combo != current_combo:  # Only register if it's a new combo
                        kbd.press(chords[current_combo])
                        kbd.release_all()
                        pending_combo = current_combo
                        last_combo_time = current_time
                        time.sleep(cooldown_time)  # Cooldown to prevent accidental repeats
    else:
        # Reset pending combo and hold time when all keys are released
        if last_release_time == 0 or (current_time - last_release_time) >= release_time_window:
            pending_combo = None
            last_hold_time = 0
            last_release_time = current_time

def check_encoder():
    global last_position, toggle_state, button_held

    # Read encoder position
    position = encoder_pos.position

    if position != last_position:
        if position > last_position:
            kbd.press(Keycode.PAGE_UP)  # Page up
        else:
            kbd.press(Keycode.PAGE_DOWN)  # Page down
        kbd.release_all()  # Release the key
        last_position = position

    # Check if the button is pressed and handle the toggle
    if not button.value and not button_held:
        button_held = True
        if toggle_state:
            neo_off()
        else:
            neo_init()
        toggle_state = not toggle_state  # Toggle the state

    # Reset button held state when the button is released
    if button.value and button_held:
        button_held = False

# Function to handle NeoKey behavior
def handle_neokey_behavior(neokey1, neokey2, pressed_keys):

    # Check each key on the first NeoKey
    for i in range(4):
        # Key is pressed
        if neokey1[i]:
            neokey1.pixels[i] = white_color  # Turn on the NeoPixel when pressed
            pressed_keys[i] = True  # Mark the key as pressed

        # Key is released
        else:
            if pressed_keys[i]:  # If the key was previously pressed
                neokey1.pixels[i] = uv_color  # Turn off the NeoPixel when released
                pressed_keys[i] = False  # Mark the key as released
                neo_init()

    # Check each key on the second NeoKey
    for i in range(4):
        # Key is pressed
        if neokey2[i]:
            # Adjust index for NeoKey2 (keys 4-7)
            neokey2.pixels[i] = white_color  # Turn on the NeoPixel when pressed
            pressed_keys[i + 4] = True  # Mark the key as pressed

        # Key is released
        else:
            if pressed_keys[i + 4]:  # If the key was previously pressed
                pressed_keys[i + 4] = False  # Mark the key as released
                neo_init()


# light 'em up
neo_init()

while True:

    check_encoder()

    handle_neokey_behavior(neokey1, neokey2, pressed_keys)

    check_chords()

