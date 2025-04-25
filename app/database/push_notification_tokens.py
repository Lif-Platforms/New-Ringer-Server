from connections import get_connection
import exceptions

async def add_mobile_notifications_device(push_token: str, account: str) -> None:
    """
    ## Add Mobile Notifications Device
    Register a mobile device for Expos push notifications API.

    ### Parameters
    - push_token: The unique identifier needed to send a notification to the device.

    - account: The account the device is being registered to.

    ### Returns
    None
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Ensure registration doesn't already exist
    cursor.execute("SELECT push_token FROM push_notifications WHERE push_token = %s", (push_token,))
    database_push_token = cursor.fetchone()

    if database_push_token:
        # Update expiration date
        cursor.execute("""
            UPDATE push_notifications
            SET expires = DATE_ADD(NOW(), INTERVAL 30 DAY)
            WHERE push_token = %s;
        """, (push_token,))
        conn.commit()
    else:
        cursor.execute("""
            INSERT INTO push_notifications (push_token, account, expires) 
            VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 30 DAY))
        """, (push_token, account,))
        conn.commit()

    # Close db connection once complete
    conn.close()

async def remove_mobile_notifications_device(push_token: str) -> None:
    """
    ## Remove Mobile Notifications Device
    Unregister a mobile device for Expos push notifications API.

    ### Parameters
    - push_token: The unique identifier needed to send a notification to the device.

    - account: The account the device is registered to.

    ### Returns
    None
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM push_notifications WHERE push_token = %s", (push_token,))
    conn.commit()
    conn.close()

async def get_mobile_push_token(account: str) -> list:
    """
    ## Get Mobile Push Token
    Get the expo push token for a mobile device.

    ### Parameters
    - account: The account you want to grab devices for.

    ### Returns
    list: All expo push tokens for an account.
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Get all tokens from database
    cursor.execute("SELECT push_token FROM push_notifications WHERE account = %s", (account,))
    tokens = cursor.fetchall()
    conn.close()

    format_tokens = []

    # Format results
    for token in tokens:
        format_tokens.append(token[0])

    return format_tokens