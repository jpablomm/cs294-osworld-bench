#!/usr/bin/env python3
"""
Deploy Qwen3-VL model to Vertex AI.

This script deploys the Qwen3-VL model from Google's Model Garden to a Vertex AI endpoint.
The model supports vision and is excellent for GUI automation tasks.

Available models:
- qwen3-vl-30b-a3b-instruct-fp8     (30B params, 3B active, FP8 - faster, cheaper)
- qwen3-vl-30b-a3b-instruct         (30B params, 3B active, full precision)
- qwen3-vl-30b-a3b-thinking-fp8     (30B params, thinking mode, FP8)
- qwen3-vl-30b-a3b-thinking         (30B params, thinking mode)
- qwen3-vl-235b-a22b-instruct-fp8   (235B params, 22B active, FP8 - recommended)
- qwen3-vl-235b-a22b-instruct       (235B params, 22B active, full precision)
- qwen3-vl-235b-a22b-thinking-fp8   (235B params, thinking mode, FP8)
- qwen3-vl-235b-a22b-thinking       (235B params, thinking mode)

Usage:
    python scripts/vertex-ai/deploy_qwen3_vl.py --project YOUR_PROJECT_ID --region us-central1

Prerequisites:
    pip install google-cloud-aiplatform
    gcloud auth application-default login
"""

import argparse
import sys


def deploy_qwen3_vl(
    project_id: str,
    region: str = "us-central1",
    model_variant: str = "qwen3-vl-235b-a22b-instruct-fp8",
) -> str:
    """
    Deploy Qwen3-VL to Vertex AI and return the endpoint URL.

    Args:
        project_id: GCP project ID
        region: GCP region (default: us-central1)
        model_variant: Model variant to deploy

    Returns:
        The endpoint URL for inference
    """
    try:
        import vertexai
        from vertexai import model_garden
    except ImportError:
        print("Error: google-cloud-aiplatform not installed.")
        print("Run: pip install google-cloud-aiplatform")
        sys.exit(1)

    print(f"Initializing Vertex AI...")
    print(f"  Project: {project_id}")
    print(f"  Region: {region}")
    print(f"  Model: qwen/qwen3-vl@{model_variant}")

    vertexai.init(project=project_id, location=region)

    # Load the model from Model Garden
    model_path = f"qwen/qwen3-vl@{model_variant}"
    print(f"\nLoading model from Model Garden: {model_path}")
    model = model_garden.OpenModel(model_path)

    # Deploy to endpoint (this creates the endpoint automatically)
    print("\nDeploying model to endpoint...")
    print("This may take 10-30 minutes depending on the model size.")
    endpoint = model.deploy()

    # Get the endpoint URL
    endpoint_url = f"https://{region}-aiplatform.googleapis.com/v1/{endpoint.resource_name}"

    print("\n" + "=" * 60)
    print("Deployment successful!")
    print("=" * 60)
    print(f"\nEndpoint resource name: {endpoint.resource_name}")
    print(f"\nFor OpenAI-compatible inference, use this base URL:")
    print(f"  {endpoint_url}")
    print("\nSet this in your environment:")
    print(f'  export QWEN3_VL_ENDPOINT_URL="{endpoint_url}"')
    print("\nOr add to .env:")
    print(f'  QWEN3_VL_ENDPOINT_URL={endpoint_url}')
    print("=" * 60)

    return endpoint_url


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Qwen3-VL model to Vertex AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available model variants:
  30B models (faster, cheaper):
    qwen3-vl-30b-a3b-instruct-fp8    - Instruct mode, FP8 quantized
    qwen3-vl-30b-a3b-instruct        - Instruct mode, full precision
    qwen3-vl-30b-a3b-thinking-fp8    - Thinking mode, FP8 quantized
    qwen3-vl-30b-a3b-thinking        - Thinking mode, full precision

  235B models (more capable):
    qwen3-vl-235b-a22b-instruct-fp8  - Instruct mode, FP8 (RECOMMENDED)
    qwen3-vl-235b-a22b-instruct      - Instruct mode, full precision
    qwen3-vl-235b-a22b-thinking-fp8  - Thinking mode, FP8
    qwen3-vl-235b-a22b-thinking      - Thinking mode, full precision

Examples:
  # Deploy recommended model (235B instruct FP8)
  python deploy_qwen3_vl.py --project my-project

  # Deploy smaller model for testing
  python deploy_qwen3_vl.py --project my-project --model qwen3-vl-30b-a3b-instruct-fp8

  # Deploy thinking model for complex reasoning
  python deploy_qwen3_vl.py --project my-project --model qwen3-vl-235b-a22b-thinking-fp8
"""
    )

    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID"
    )
    parser.add_argument(
        "--region",
        default="us-central1",
        help="GCP region (default: us-central1)"
    )
    parser.add_argument(
        "--model",
        default="qwen3-vl-235b-a22b-instruct-fp8",
        choices=[
            "qwen3-vl-30b-a3b-instruct-fp8",
            "qwen3-vl-30b-a3b-instruct",
            "qwen3-vl-30b-a3b-thinking-fp8",
            "qwen3-vl-30b-a3b-thinking",
            "qwen3-vl-235b-a22b-instruct-fp8",
            "qwen3-vl-235b-a22b-instruct",
            "qwen3-vl-235b-a22b-thinking-fp8",
            "qwen3-vl-235b-a22b-thinking",
        ],
        help="Model variant to deploy (default: qwen3-vl-235b-a22b-instruct-fp8)"
    )

    args = parser.parse_args()

    deploy_qwen3_vl(
        project_id=args.project,
        region=args.region,
        model_variant=args.model,
    )


if __name__ == "__main__":
    main()
