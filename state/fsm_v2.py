import logging
from transitions import Machine

logger = logging.getLogger("ladas.fsm")

class LADASStateMachine:
    """
    State machine for LADAS utilizing the 'transitions' library.
    Ensures strict validation and prevents state bleeding.
    """
    
    states = [
        'idle',
        'parsing',
        'planning',
        'executing',
        'validating',
        'retrying',
        'task_complete',
        'failed',
        'timeout',
        'aborted'
    ]

    def __init__(self):
        self.machine = Machine(
            model=self, 
            states=LADASStateMachine.states, 
            initial='idle',
            send_event=True  # Pass event data to callbacks if needed
        )
        
        # Define strict valid transitions
        
        # From Idle
        self.machine.add_transition(trigger='start_parsing', source='idle', dest='parsing', after='_log_state')
        
        # Core Lifecycle
        self.machine.add_transition(trigger='to_planning', source='parsing', dest='planning', after='_log_state')
        self.machine.add_transition(trigger='start_executing', source='planning', dest='executing', after='_log_state')
        
        # Execution loop
        self.machine.add_transition(trigger='start_validating', source='executing', dest='validating', after='_log_state')
        self.machine.add_transition(trigger='failed_validation', source='validating', dest='retrying', after='_log_state')
        self.machine.add_transition(trigger='retry_to_executing', source='retrying', dest='executing', after='_log_state')
        self.machine.add_transition(trigger='finish_validating', source='validating', dest='executing', after='_log_state') # next step 
        
        # Terminal states
        self.machine.add_transition(trigger='complete', source='*', dest='task_complete', after='_log_state')
        self.machine.add_transition(trigger='fail', source='*', dest='failed', after='_log_state')
        self.machine.add_transition(trigger='timeout', source='*', dest='timeout', after='_log_state')
        self.machine.add_transition(trigger='trigger_failsafe', source='*', dest='aborted', after='_log_state')

    def _log_state(self, event):
        source = event.transition.source
        dest = event.transition.dest
        logger.debug(f"FSM Transition: {source} -> {dest}")

    def on_enter_executing(self, event):
        # Cleanup/Setup hooks specifically when hitting executing loop
        pass

    def on_exit_validating(self, event):
        # Ensure temporary screenshot assets for validation are flagged for cleanup
        pass
