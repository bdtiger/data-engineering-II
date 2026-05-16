import sys
import syft as sy

if len(sys.argv) < 2:
    print("Usage: python syft_start_server.py <name>")
    sys.exit(1)

node_name = sys.argv[1]

node = sy.orchestra.launch(
    name=node_name,
    port=8080,
    dev_mode=True, # bypasses manual UI approval — required for simulation
    reset=True
)

print(f"Datasite {node_name} running on port 8080...")
input("Press Enter to stop...\n")