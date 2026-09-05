from backend.app.intelligence.llm_client import OllamaClient


def main():

    print()
    print("=" * 70)
    print("OLLAMA CONNECTION TEST")
    print("=" * 70)

    client = OllamaClient(
        model="gemma:2b"
    )

    prompt = """
You are a financial investigation assistant.

Explain in one short paragraph what a payment
settlement reconciliation exception means.

Do not use bullet points.
"""

    print()
    print("Model: gemma:2b")
    print("Sending request to Ollama...")
    print()

    response = client.generate(prompt)

    print("MODEL RESPONSE")
    print("-" * 70)
    print(response)

    print()
    print("=" * 70)
    print("OLLAMA TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
