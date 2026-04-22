"""
Task 4: Merger Consumer

Subscribes to the 'results-topic'. Collects converted words with original index. 
Once all words for a job have arrived it reassembles them in order and prints the final converted string.
"""

import json
import pulsar


def main():
    client   = pulsar.Client('pulsar://localhost:6650')
    consumer = client.subscribe(
        'results-topic',
        subscription_name='merger-sub',
    )

    print("Merger waiting for converted words...")

    jobs = {}  # job_id -> {"words": {index: word}, "total": int}

    while True:
        msg = consumer.receive()
        try:
            data   = json.loads(msg.data().decode("utf-8"))
            job_id = data["job_id"]
            index  = data["index"]
            word   = data["word"]
            total  = data["total"]

            print(f"Merger received word[{index}] = '{word}' (job: {job_id})")

            if job_id not in jobs:
                jobs[job_id] = {"words": {}, "total": total}
            jobs[job_id]["words"][index] = word

            if len(jobs[job_id]["words"]) == jobs[job_id]["total"]:
                merged = " ".join(jobs[job_id]["words"][i] for i in range(total))
                print(f"Merged result (job: {job_id}): '{merged}'")
                del jobs[job_id]

            consumer.acknowledge(msg)

        except Exception as e:
            print(f"Merger error: {e}")
            consumer.negative_acknowledge(msg)


if __name__ == "__main__":
    main()
