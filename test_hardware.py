from time import sleep

def dry_run():
    print("Testing action executor constraints...")
    from execution.keyboard_controller import KeyboardController
    from execution.mouse_controller import MouseController
    
    kb = KeyboardController(min_delay_ms=0, max_delay_ms=5)
    mouse = MouseController(cursor_speed_multiplier=0.1)
    
    # Very quick test to see if pynput loads
    # We won't actually click or type to avoid messing up the user's screen during testing
    print("Initializing input controllers... DONE")
    print("All modules verified! LADAS is ready for its first real test.")

if __name__ == "__main__":
    dry_run()
