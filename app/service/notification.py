from firebase_admin import messaging


def send_push_notification(token: str, title: str, body: str):
    if not token:
        return

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=token,
    )

    messaging.send(message)
