"""
Task 2: Producer

Create a Pulsar producer that sends a message to a topic.
"""

import pulsar


def main():
    # Create a pulsar client by supplying ip address and port
    client = pulsar.Client('pulsar://localhost:6650')
    # Create a producer on the topic that consumer can subscribe to
    producer = client.create_producer('DEtopic')
    # Send a message to consumer
    producer.send(('Welcome to Data Engineering Course!').encode('utf-8'))
    # Destroy pulsar client
    client.close()


if __name__ == "__main__":
    main()
