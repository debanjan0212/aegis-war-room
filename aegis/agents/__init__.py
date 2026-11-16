"""The agents. One file each, and every file has the same three parts:

PROMPT     what the agent is asked to do when a cloud model is switched on
offline()  the built-in rules used when the model toggle is "offline" (or the model fails)
run()      the step in the flow: gather facts, ask the brain, tell the room, pass results on
"""
