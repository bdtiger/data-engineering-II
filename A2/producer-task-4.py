"""
Task 4: Producer (Splitter)

Splits the INPUT_STRING into individual words and publishes each word as a separate Pulsar message to the 'words-topic' topic.  
Every message contains a JSON payload:
  - job_id : unique identifier for this processing job
  - index  : position of the word in the original string
  - word   : the individual word to be processed
    - total  : total number of words in the original string (for merger to know when all words have arrived)
"""

import json
import uuid
import pulsar

INPUT_STRING = "I am working on assignement 2 for DE-II. I want to be capatilized"

def main():
    words   = INPUT_STRING.split()
    job_id  = str(uuid.uuid4())

    client   = pulsar.Client('pulsar://localhost:6650')
    producer = client.create_producer("words-topic")

    print(f"Producer Job: {job_id}")
    print(f"Producer Splitting '{INPUT_STRING}' into {len(words)} words ...")

    for index, word in enumerate(words):
        payload = json.dumps({
            "job_id": job_id,
            "index":  index,
            "word":   word,
            "total":  len(words),
        }).encode("utf-8")

        producer.send(payload)
        print(f"Producer sent word[{index}] = '{word}'")

    print("All words published.")
    client.close()


if __name__ == "__main__":
    main()
