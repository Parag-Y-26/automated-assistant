import math
import random
import time
from execution.failsafe_monitor import failsafe

class MotionAnimator:
    """Handles generating human-like mouse paths using Bezier curves."""
    
    def __init__(self, 
                 cursor_speed_multiplier=1.0, 
                 bezier_variance=0.2, 
                 min_duration_ms=200, 
                 max_duration_ms=1200,
                 click_offset_px=3):
        self.cursor_speed_multiplier = cursor_speed_multiplier
        self.bezier_variance = bezier_variance
        self.min_duration = min_duration_ms / 1000.0
        self.max_duration = max_duration_ms / 1000.0
        self.click_offset = click_offset_px

    def _get_distance(self, p1, p2):
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    def _calculate_duration(self, distance):
        """Calculate duration based on distance, bounded by min/max."""
        # Baseline: ~1000 pixels takes ~0.8 seconds at 1.0 multiplier
        base_time = (distance / 1000.0) * 0.8
        duration = base_time * self.cursor_speed_multiplier
        
        # Add slight jitter (±10%)
        duration = duration * random.uniform(0.9, 1.1)
        
        return max(self.min_duration, min(duration, self.max_duration))

    def _generate_bezier_curve(self, start, end, num_points):
        """Generate a cubic Bezier curve with randomized control points."""
        x1, y1 = start
        x4, y4 = end
        
        # Calculate distance
        distance = self._get_distance(start, end)
        
        # Calculate control points roughly along the line but perturbed
        # The variance is proportional to the distance
        variance = distance * self.bezier_variance
        
        # Midpoints for control
        mid_x1 = x1 + (x4 - x1) * 0.33
        mid_y1 = y1 + (y4 - y1) * 0.33
        
        mid_x2 = x1 + (x4 - x1) * 0.66
        mid_y2 = y1 + (y4 - y1) * 0.66
        
        # Add random perpendicular variance
        cx1 = mid_x1 + random.uniform(-variance, variance)
        cy1 = mid_y1 + random.uniform(-variance, variance)
        
        cx2 = mid_x2 + random.uniform(-variance, variance)
        cy2 = mid_y2 + random.uniform(-variance, variance)

        points = []
        for i in range(num_points):
            t = i / max(1, (num_points - 1))
            
            # Ease-in / Ease-out function for t (smoothstep interpolation)
            # This makes the mouse accelerate then decelerate
            t_ease = t * t * (3 - 2 * t) 
            
            # Cubic bezier formula
            x = (1 - t_ease)**3 * x1 + 3 * (1 - t_ease)**2 * t_ease * cx1 + 3 * (1 - t_ease) * t_ease**2 * cx2 + t_ease**3 * x4
            y = (1 - t_ease)**3 * y1 + 3 * (1 - t_ease)**2 * t_ease * cy1 + 3 * (1 - t_ease) * t_ease**2 * cy2 + t_ease**3 * y4
            
            points.append((int(x), int(y)))
            
        return points

    def move_mouse(self, start_pos, end_pos, mouse_controller):
        """
        Move the mouse from start to end using a Bezier curve.
        `mouse_controller` should be the pynput Controller.
        """
        # Add a tiny random offset to the target to avoid pixel-perfect clicks
        offset_x = random.randint(-self.click_offset, self.click_offset)
        offset_y = random.randint(-self.click_offset, self.click_offset)
        target = (end_pos[0] + offset_x, end_pos[1] + offset_y)
        
        distance = self._get_distance(start_pos, target)
        
        if distance < 5:
            # Too close, just snap
            mouse_controller.position = target
            time.sleep(random.uniform(0.05, 0.1))
            return

        duration = self._calculate_duration(distance)
        
        # How many update frames? Let's aim for ~60 FPS
        num_points = max(10, int(duration * 60))
        
        curve_points = self._generate_bezier_curve(start_pos, target, num_points)
        
        sleep_time = duration / num_points
        
        for point in curve_points:
            failsafe.check()
            mouse_controller.position = point
            time.sleep(sleep_time)
            
        # Final safety snap (due to integer rounding in curve generation)
        mouse_controller.position = target
        time.sleep(random.uniform(0.02, 0.05))
