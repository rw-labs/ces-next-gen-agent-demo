gcloud iam service-accounts create live-agent-backend \
  --display-name="Live Agent Backend" \
  --project="hello-world-418507"

curl -X POST http://localhost:8080/callback \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "'$SESSION_ID'",
    "agentMessage": "Hello from callback!",
    "manager_approved": true
  }'