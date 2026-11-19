#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
REPOSITORY="${ECR_REPOSITORY:-paymentpulse}"
TAG="${IMAGE_TAG:-latest}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

if ! aws ecr describe-repositories --repository-names "$REPOSITORY" --region "$REGION" >/dev/null 2>&1; then
  aws ecr create-repository --repository-name "$REPOSITORY" --region "$REGION" \
    --image-scanning-configuration scanOnPush=true >/dev/null
fi

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker build -t "${REPOSITORY}:${TAG}" ./app
docker tag "${REPOSITORY}:${TAG}" "${REGISTRY}/${REPOSITORY}:${TAG}"
docker push "${REGISTRY}/${REPOSITORY}:${TAG}"

echo "Image pushed: ${REGISTRY}/${REPOSITORY}:${TAG}"
echo "Use this exact URI for terraform/terraform.tfvars container_image."
