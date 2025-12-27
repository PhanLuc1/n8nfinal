from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps

load_dotenv()

app = Flask(__name__)
CORS(app)

FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FB_API_VERSION = os.getenv("FB_API_VERSION", "v20.0")
API_KEY = os.getenv("API_KEY")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def require_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not API_KEY:
            return f(*args, **kwargs)
        if request.headers.get("X-API-Key") != API_KEY:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return wrapper


@app.route("/")
def home():
    return jsonify({"service": "Facebook API Backend", "status": "running"})


@app.route("/health")
def health():
    return jsonify({"status": "OK", "time": datetime.utcnow().isoformat()})


@app.route("/api/facebook/post", methods=["POST"])
@require_api_key
def post_text():
    data = request.json or {}
    message = data.get("message")
    link = data.get("link")

    if not message:
        return jsonify({"success": False, "error": "message required"}), 400

    payload = {"message": message}
    if link:
        payload["link"] = link

    r = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/feed",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json=payload
    )

    return jsonify({"success": r.status_code == 200, "data": r.json()}), r.status_code


@app.route("/api/facebook/post-photo", methods=["POST"])
@require_api_key
def post_photo():
    data = request.json or {}
    image_url = data.get("image_url")
    message = data.get("message", "")

    if not image_url:
        return jsonify({"success": False, "error": "image_url required"}), 400

    r = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json={"url": image_url, "message": message}
    )

    return jsonify({"success": r.status_code == 200, "data": r.json()}), r.status_code


@app.route("/api/facebook/post-video", methods=["POST"])
@require_api_key
def post_video():
    data = request.json or {}
    video_url = data.get("video_url")
    title = data.get("title", "")
    description = data.get("description", "")

    if not video_url:
        return jsonify({"success": False, "error": "video_url required"}), 400

    r = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/videos",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json={
            "file_url": video_url,
            "title": title,
            "description": description
        }
    )

    return jsonify({"success": r.status_code == 200, "data": r.json()}), r.status_code


@app.route("/api/facebook/post-video-thumbnail", methods=["POST"])
@require_api_key
def post_video_with_thumbnail():
    data = request.json or {}
    video_url = data.get("video_url")
    thumb_url = data.get("thumb_url")
    caption = data.get("caption", "")

    if not video_url:
        return jsonify({"success": False, "error": "video_url required"}), 400

    payload = {
        "file_url": video_url,
        "description": caption
    }

    if thumb_url:
        payload["thumb"] = thumb_url

    r = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/videos",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json=payload
    )

    return jsonify({
        "success": r.status_code == 200,
        "data": r.json()
    }), r.status_code


@app.route("/api/facebook/post-media", methods=["POST"])
@require_api_key
def post_media():
    data = request.json or {}
    video_url = data.get("video_url")
    image_urls = data.get("image_urls", [])
    caption = data.get("caption", "")
    post_type = data.get("post_type", "auto")

    if post_type == "auto":
        if video_url and image_urls:
            post_type = "video_with_photo"
        elif video_url:
            post_type = "video"
        elif len(image_urls) > 1:
            post_type = "carousel"
        elif len(image_urls) == 1:
            post_type = "photo"
        else:
            return jsonify({
                "success": False,
                "error": "No media provided"
            }), 400

    if post_type == "video":
        return _post_video_only(video_url, caption)
    elif post_type == "photo":
        return _post_photo_only(image_urls[0], caption)
    elif post_type == "carousel":
        return _post_carousel(image_urls, caption)
    elif post_type == "video_with_photo":
        return _post_video_with_photo(video_url, image_urls, caption)
    else:
        return jsonify({
            "success": False,
            "error": "Invalid post_type"
        }), 400


def _post_video_only(video_url, caption):
    r = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/videos",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json={
            "file_url": video_url,
            "description": caption
        }
    )
    return jsonify({
        "success": r.status_code == 200,
        "post_type": "video",
        "data": r.json()
    }), r.status_code


def _post_photo_only(image_url, caption):
    r = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json={
            "url": image_url,
            "message": caption
        }
    )
    return jsonify({
        "success": r.status_code == 200,
        "post_type": "photo",
        "data": r.json()
    }), r.status_code


def _post_carousel(image_urls, caption):
    photo_ids = []
    for img_url in image_urls[:10]:
        r = requests.post(
            f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos",
            headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
            json={
                "url": img_url,
                "published": False
            }
        )
        if r.status_code == 200:
            photo_ids.append({"media_fbid": r.json()["id"]})

    r = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/feed",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json={
            "message": caption,
            "attached_media": photo_ids
        }
    )

    return jsonify({
        "success": r.status_code == 200,
        "post_type": "carousel",
        "photos_count": len(photo_ids),
        "data": r.json()
    }), r.status_code


def _post_video_with_photo(video_url, image_urls, caption):
    r1 = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/videos",
        headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
        json={
            "file_url": video_url,
            "description": caption
        }
    )

    if r1.status_code != 200:
        return jsonify({
            "success": False,
            "error": "Failed to post video",
            "data": r1.json()
        }), r1.status_code

    post_id = r1.json().get("id")

    if image_urls:
        comment_text = "📸 Ảnh liên quan:\n" + "\n".join(image_urls[:3])

        r2 = requests.post(
            f"https://graph.facebook.com/{FB_API_VERSION}/{post_id}/comments",
            headers={"Authorization": f"Bearer {FB_ACCESS_TOKEN}"},
            json={"message": comment_text}
        )

        return jsonify({
            "success": True,
            "post_type": "video_with_photo",
            "video_post": r1.json(),
            "photo_comment": r2.json() if r2.status_code == 200 else None
        }), 200

    return jsonify({
        "success": True,
        "post_type": "video",
        "data": r1.json()
    }), 200


def fetch_post_metrics(post_id):
    r = requests.get(
        f"https://graph.facebook.com/{FB_API_VERSION}/{post_id}",
        params={
            "fields": (
                "likes.limit(0).summary(true),"
                "comments.limit(0).summary(true),"
                "reactions.limit(0).summary(true),"
                "shares"
            ),
            "access_token": FB_ACCESS_TOKEN
        }
    )
    return r.json() if r.status_code == 200 else {}


@app.route("/api/facebook/post-ids", methods=["GET"])
@require_api_key
def get_post_ids():
    limit = request.args.get("limit", 50)

    r = requests.get(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/posts",
        params={
            "fields": "id",
            "limit": limit,
            "access_token": FB_ACCESS_TOKEN
        }
    )

    if r.status_code != 200:
        return jsonify({
            "success": False,
            "error": r.json()
        }), r.status_code

    post_ids = [p["id"] for p in r.json().get("data", [])]

    return jsonify({
        "success": True,
        "total": len(post_ids),
        "post_ids": post_ids
    })


@app.route("/api/facebook/post-analytics/<post_id>", methods=["GET"])
@require_api_key
def post_analytics(post_id):
    data = fetch_post_metrics(post_id)

    if "error" in data:
        return jsonify({"success": False, "error": data["error"]}), 400

    likes = data.get("likes", {}).get("summary", {}).get("total_count", 0)
    comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
    reactions = data.get("reactions", {}).get("summary", {}).get("total_count", 0)
    shares = data.get("shares", {}).get("count", 0)

    return jsonify({
        "success": True,
        "post_id": post_id,
        "metrics": {
            "likes": likes,
            "comments": comments,
            "reactions": reactions,
            "shares": shares,
            "engagement": likes + comments + reactions + shares
        }
    })


@app.route("/api/facebook/posts-analytics", methods=["GET"])
@require_api_key
def posts_analytics():
    limit = request.args.get("limit", 10)

    r = requests.get(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/posts",
        params={
            "limit": limit,
            "fields": "id",
            "access_token": FB_ACCESS_TOKEN
        }
    )

    if r.status_code != 200:
        return jsonify({"success": False, "error": r.json()}), r.status_code

    results = []

    for p in r.json().get("data", []):
        metrics = fetch_post_metrics(p["id"])

        likes = metrics.get("likes", {}).get("summary", {}).get("total_count", 0)
        comments = metrics.get("comments", {}).get("summary", {}).get("total_count", 0)
        reactions = metrics.get("reactions", {}).get("summary", {}).get("total_count", 0)
        shares = metrics.get("shares", {}).get("count", 0)

        results.append({
            "post_id": p["id"],
            "likes": likes,
            "comments": comments,
            "reactions": reactions,
            "shares": shares,
            "engagement": likes + comments + reactions + shares
        })

    results.sort(key=lambda x: x["engagement"], reverse=True)

    return jsonify({"success": True, "posts": results})


if __name__ == "__main__":
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        raise RuntimeError("Missing FB_PAGE_ID or FB_ACCESS_TOKEN")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)