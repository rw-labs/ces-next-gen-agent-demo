context-file:
	(cd ces/backend && \
	find . -type f \( -iname "*.py" -o -iname "*.js" -o -iname "*.html" \) -not -path "./server/.venv/*" -print0 | \
	xargs -0 -I {} sh -c 'printf "=== %s ===\n" "{}"; cat "{}"' \
	) > code-context.txt

context-file-py:
	(cd ces/backend && \
	find . -type f \( -iname "*.py" \) -not -path "./server/.venv/*" -print0 | \
	xargs -0 -I {} sh -c 'printf "=== %s ===\n" "{}"; cat "{}"' \
	) > code-context.txt
	
client-local:
	(cd "ces/backend/client/" && uv run python -m http.server 8000)

backend-local:
	(cd "ces/backend/server/" && uv run combined_server.py)

client-cloudrun-deploy:
	(cd ces/backend && gcloud builds submit --config client/cloudbuild.yaml)

backend-cloudrun-deploy:
	(cd ces/backend && gcloud builds submit --config server/cloudbuild_optus_modem.yaml)
