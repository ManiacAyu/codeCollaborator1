import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

class QuizConsumer(AsyncWebsocketConsumer):
    user_room_map = {}  # ✅ Dictionary to store users per room

    async def connect(self):
        """Handle new WebSocket connection."""
        self.channel_layer = get_channel_layer()
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"quiz_{self.room_name}"

        # Add socket to room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"✅ WebSocket Connected: {self.room_name}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.room_name in self.user_room_map:
            # Remove user from room
            self.user_room_map[self.room_name].pop(self.channel_name, None)
            
            # Notify others in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_disconnected",
                    "socket_id": self.channel_name,
                },
            )
            
            # If the room is empty, remove it
            if not self.user_room_map[self.room_name]:
                del self.user_room_map[self.room_name]

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print(f"🔴 WebSocket Disconnected: {self.room_name}")

    async def receive(self, text_data):
        """Handle messages received from the client."""
        try:
            data = json.loads(text_data)
            print(f"📩 Received WebSocket Data: {data}")

            action = data.get("action")

            if action == "join":
                username = data.get("username", "Anonymous")

                # ✅ Ensure the room exists in the map
                if self.room_name not in self.user_room_map:
                    self.user_room_map[self.room_name] = {}

                # ✅ Add user to the correct room
                self.user_room_map[self.room_name][self.channel_name] = username

                # ✅ Get the correct users for the room
                clients = [
                    {"socketId": sid, "username": name}
                    for sid, name in self.user_room_map[self.room_name].items()
                ]
                print("Recieved")
                # Notify all users in the room about the new user
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "user_joined",
                        "clients": clients,
                        "username": username,
                        "socket_id": self.channel_name,
                    },
                )

            elif action == "code-change":
                code = data.get("code", "")

                # Broadcast code change to all users in the room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "broadcast_code", "code": code},
                )

        except json.JSONDecodeError:
            print("❌ ERROR: Received invalid JSON!")
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")

    async def user_joined(self, event):
        """Broadcast the joined event to all users in the room."""
        print("user_joined")
        print(event["clients"])
        await self.send(text_data=json.dumps({
            "action": "joined",
            "clients": event["clients"],  # Send updated client list
            "username": event["username"],  # Notify about the new user
            "socket_id": event["socket_id"],  # Send the joining user's ID
        }))

    async def user_disconnected(self, event):
        """Notify clients when a user disconnects."""
        await self.send(text_data=json.dumps({"action": "disconnected", **event}))

    async def broadcast_code(self, event):
        """Broadcast code changes to all connected users."""
        await self.send(text_data=json.dumps({"action": "code-change", "code": event["code"]}))
