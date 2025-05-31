import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import atexit
import time

app = Flask(__name__)
CORS(app)

# Detect if running on Raspberry Pi (set this env var true on Pi)
RUNNING_ON_PI = os.environ.get("RUNNING_ON_PI", "false").lower() == "true"

if RUNNING_ON_PI:
    import pigpio
    pi = pigpio.pi()
else:
    class MockPi:
        def set_mode(self, pin, mode): pass
        def write(self, pin, value): pass
        def set_servo_pulsewidth(self, pin, pulse): pass
        def stop(self): pass
    pi = MockPi()

lights = {"bedroom": 23, "garage": 4, "display": 22, "ground": 10, "function": 21}
servo_pins = {
    "entrance": 18,
    "exit": 19
}

# Initialize light pins
for pin in lights.values():
    pi.set_mode(pin, 1)  # pigpio.OUTPUT = 1
    pi.write(pin, 0)

# Initialize servo pins
for pin in servo_pins.values():
    pi.set_mode(pin, 1)
    pi.set_servo_pulsewidth(pin, 0)

@app.route("/", methods=["POST", "GET"])
def alexa_handler():
    if request.method == "GET":
        return jsonify({"message": "Smart Home API is running"}), 200

    data = request.get_json()
    if not data or "request" not in data:
        return jsonify(response("Invalid request. Please send a valid Alexa request."))

    req_type = data["request"]["type"]

    if req_type == "LaunchRequest":
        return jsonify(response("Welcome to Smart Home Automation!"))

    elif req_type == "IntentRequest":
        intent_name = data["request"]["intent"]["name"]

        if intent_name == "TurnOnLightIntent":
            location = data["request"]["intent"]["slots"].get("LightLocation", {}).get("value", "all")
            success = control_lights(location, "on")	
            return jsonify(response(f"Turning on {location} light." if success else "Failed to turn on light."))

        elif intent_name == "TurnOffLightIntent":
            location = data["request"]["intent"]["slots"].get("LightLocation", {}).get("value", "all")
            success = control_lights(location, "off")
            return jsonify(response(f"Turning off {location} light." if success else "Failed to turn off light."))

        elif intent_name == "OpenEntranceGateIntent":
            success = control_gate("open", "entrance")
            return jsonify(response("Opening entrance gate." if success else "Failed to open entrance gate."))

        elif intent_name == "CloseEntranceGateIntent":
            success = control_gate("close", "entrance")
            return jsonify(response("Closing entrance gate." if success else "Failed to close entrance gate."))

        elif intent_name == "OpenExitGateIntent":
            success = control_gate("open", "exit")
            return jsonify(response("Opening exit gate." if success else "Failed to open exit gate."))

        elif intent_name == "CloseExitGateIntent":
            success = control_gate("close", "exit")
            return jsonify(response("Closing exit gate." if success else "Failed to close exit gate."))

        elif intent_name == "CloseBothGatesIntent":  # Close both gates
            success = control_both_gates("close")
            return jsonify(response("Closing both gates." if success else "Failed to close both gates."))

        elif intent_name == "OpenBothGatesIntent":  # Open both gates
            success = control_both_gates("open")
            return jsonify(response("Opening both gates." if success else "Failed to open both gates."))

    return jsonify(response("I didn't understand that."))

@app.route("/gate/<gate>/<action>", methods=["GET"])
def api_control_gate(gate, action):
    success = control_gate(action, gate)
    return jsonify({"message": f"{gate.capitalize()} gate {action}ed." if success else f"Failed to {action} {gate} gate."})

def response(output_speech):
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": output_speech,
            },
            "shouldEndSession": True
        }
    }

def control_all_lights(action):
    try:
        for location, pin in lights.items():
            pi.write(pin, 1 if action == "on" else 0)
        return True
    except Exception as e:
        print(f"Error controlling all lights: {e}")
        return False

def control_lights(location, action):
    upstairs_lights = ["function", "bedroom"]
    downstairs_lights = ["display", "ground", "garage"]

    try:
        if location == "all":
            return control_all_lights(action)
        elif location == "upstairs":
            for light in upstairs_lights:
                pi.write(lights[light], 1 if action == "on" else 0)
            return True
        elif location == "downstairs":
            for light in downstairs_lights:
                pi.write(lights[light], 1 if action == "on" else 0)
            return True
        elif location in lights:
            pi.write(lights[location], 1 if action == "on" else 0)
            return True
    except Exception as e:
        print(f"Error controlling light {location}: {e}")
        return False

    return False

def control_gate(action, gate):
    try:
        if gate not in servo_pins:
            print(f"Invalid gate: {gate}")
            return False

        pin = servo_pins[gate]
        print(f"Controlling {gate} gate with action: {action}")

        if action == "open":
            pulse_width = 1000 if gate == "entrance" else 2000
        elif action == "close":
            pulse_width = 2000 if gate == "entrance" else 1000
        else:
            print(f"Invalid action: {action}")
            return False

        pi.set_servo_pulsewidth(pin, pulse_width)
        time.sleep(2)
        pi.set_servo_pulsewidth(pin, 0)

        print(f"{gate.capitalize()} gate {action} complete.")
        return True
    except Exception as e:
        print(f"Error during {gate} gate {action}: {e}")
        return False

def control_both_gates(action):
    print(f"Attempting to {action} both gates...")
    success_entrance = control_gate(action, "entrance")
    success_exit = control_gate(action, "exit")
    
    if success_entrance and success_exit:
        print("Both gates successfully controlled.")
    else:
        print("One or both gates failed to respond.")
        
    return success_entrance and success_exit

def cleanup_gpio():
    for pin in lights.values():
        pi.write(pin, 0)
    for pin in servo_pins.values():
        pi.set_servo_pulsewidth(pin, 0)
    pi.stop()

atexit.register(cleanup_gpio)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
