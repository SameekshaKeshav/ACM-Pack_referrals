from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def frontend_index(request):
    """Serve the React app's index.html; React Router handles the path in the browser."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponse(
            "Frontend not built: run npm run build in frontend/.", status=503
        )
    response = FileResponse(index.open("rb"), content_type="text/html")
    # Revalidate every load so a new deploy's asset filenames are picked up.
    response["Cache-Control"] = "no-cache"
    return response
