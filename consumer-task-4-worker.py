"""
Task 4: Worker Consumer / Producer

Subscribes to the 'words-topic'. For each incoming word message it:
  1. Applies the conversion() function from conversion.py.
  2. Publishes the converted word to 'results-topic'.
"""

import json
import pulsar


def function(string):
    return string.upper()


def conversion(substring, operation):
    return operation(substring)


def main():
    client   = pulsar.Client('pulsar://localhost:6650')
    consumer = client.subscribe(
        'words-topic',
        subscription_name='workers-sub',
        consumer_type=pulsar.ConsumerType.Shared,
    )
    producer = client.create_producer('results-topic')

    print("Worker waiting for words...")

    while True:
        msg = consumer.receive()
        try:
            data  = json.loads(msg.data().decode("utf-8"))
            word  = data["word"]
            converted = conversion(word, function)

            result = json.dumps({
                "job_id": data["job_id"],
                "index":  data["index"],
                "word":   converted,
                "total":  data["total"],
            }).encode("utf-8")

            producer.send(result)
            print(f"Worker converted word[{data['index']}]: '{word}' -> '{converted}'")
            consumer.acknowledge(msg)
        except Exception as e:
            print(f"Worker error: {e}")
            consumer.negative_acknowledge(msg)


if __name__ == "__main__":
    main()
