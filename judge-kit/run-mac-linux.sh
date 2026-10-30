#!/bin/sh
# Warrant judge kit. Runs Warrant from GitHub through uv, with a small menu.
WARRANT="git+https://github.com/TheClazer/warrant"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "This needs uv, a small Python tool runner from astral.sh."
  printf "Install it now? [y/N] "
  read -r answer
  case "$answer" in
    y|Y|yes) curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH" ;;
    *) echo "Nothing installed. See https://docs.astral.sh/uv/ or use the live demo: https://warrant-demo.onrender.com"; exit 0 ;;
  esac
fi

echo
echo "WARRANT: a permission slip for your AI agent"
echo
echo "  1. See the difference        no AI, no key, about 5 seconds"
echo "  2. Guard a real command      no AI, no key"
echo "  3. The whole flow with AI    needs a Nebius Token Factory key"
echo
printf "Choose 1, 2 or 3 [1]: "
read -r choice

case "${choice:-1}" in
  2)
    echo
    echo "Allowed: example.com. This request should go through:"
    uvx --from "$WARRANT" warrant guard --allow example.com -- curl -s -o /dev/null -w "HTTP %{http_code}\n" https://example.com/
    echo
    echo "This one should be blocked (curl reports HTTP 000 because the connection was refused):"
    uvx --from "$WARRANT" warrant guard --allow example.com -- curl -s -o /dev/null -w "HTTP %{http_code}\n" https://www.iana.org/
    ;;
  3)
    uvx --from "$WARRANT" warrant try
    ;;
  *)
    uvx --from "$WARRANT" warrant prove
    ;;
esac
