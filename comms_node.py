import socket
import struct
import threading
from typing import Optional, Any
import time
import uuid
import json
from pydantic import BaseModel, Field
import typer

class CommsAgent(BaseModel):
    """ A class to enable an agent to establish a UDP publish subscriber network."""
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The ID of the agent.")
    mcast_grp:str = Field(..., description="the IP address of the multicast group.")
    mcast_port: int = Field(..., description="the port of the multicast group.")
    running: bool = Field(default=True, description="The status of the agent.")
    ttl: int = Field(default=1, description="The time to live of the multicast group.")
    sub_sock:Any = Field(default_factory = lambda:socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP), description="The subscriber socket.")
    pub_sock: Any = Field(default_factory = lambda:socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP), description="The publisher socket.")
    listener_thread: Optional[Any] = Field(default=None, description="The thread to listen for messages.")


    def __init__(self, **data):
        super().__init__(**data)
        self.sub_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sub_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1) # TODO remove this in prod, only for local testing
        self.sub_sock.bind(('0.0.0.0', self.mcast_port))
        mreq = struct.pack("=4s4s", socket.inet_aton(self.mcast_grp), socket.inet_aton('0.0.0.0'))
        self.sub_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.pub_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()
        print (f"Agent {self.agent_id} initialised.")

    def _listen_loop(self):
        """Listen for messages on the multicast group."""
        while self.running:
            try:
                data, addr = self.sub_sock.recvfrom(1024)
                message = data.decode('utf-8', errors='ignore')
                self.on_message_recieved(addr, message)
            except socket.error as e:
                print (f"Error receiving message: {e}")
                break

    def on_message_recieved(self, addr, message):
        """Method to be implemented by the agent upon receipt of a message."""
        print (f"Message from {addr}: {message}")

    def send_message(self, message: str):
        """Send a message to the multicast group."""
        full_message = {"agent_id": self.agent_id, "message": message}
        send_message = json.dumps(full_message)
        self.pub_sock.sendto(send_message.encode('utf-8'), (self.mcast_grp, self.mcast_port))
        print (f"Message sent: {message}")

    def close(self):
        """Close the sockets and stop the agent."""
        self.running = False
        self.sub_sock.close()
        self.pub_sock.close()
        print (f"Agent {self.agent_id} offline.")


def main(mcast_grp: str, mcast_port: int):
    agent = CommsAgent(mcast_grp=mcast_grp, mcast_port=mcast_port)
    print(f"Agent {agent.agent_id} running.")
    print("Enter message to send or Ctrl+C to exit.")
    try:
        while agent.running:
            message = input("Enter message: ")
            agent.send_message(message)
    except KeyboardInterrupt:
        agent.close()
        print("Exiting...")


if __name__ == "__main__":
    typer.run(main)