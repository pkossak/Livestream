import pyautogui
import cv2
import numpy as np
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from concurrent.futures import ThreadPoolExecutor
from asyncio import Queue
from channels.exceptions import StopConsumer
import time


class CameraStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        # Przekazanie wszystkich argumentów pozycyjnych i słownikowych do konstruktora rodzica
        # Czyli żeby mogło korzystać z AsyncWebsocketConsumer z django channels
        super().__init__(*args, **kwargs)
        self.executor = ThreadPoolExecutor(max_workers=1)  # 1 Wątek dla kamery
        self.queue = Queue()  # Kolejka asynchroniczna na klatki obrazu
        self.running = False  # Flaga informująca o działaniu pętli
        self.cap = None

        # Taski asynchroniczne
        self.camera_task = None  # Zadanie wątku do czytania kamery
        self.sender_task = None  # Zadanie do wysyłania klatek do klienta

    async def connect(self):
        await self.accept()       # Połączenie WebSocket
        self.running = True       # Flaga true - pętla działa

        loop = asyncio.get_event_loop()
        # Uruchomienie wątku do odczytu obrazu z kamery
        self.camera_task = loop.run_in_executor(self.executor, self.read_camera, loop)
        # Asynchroniczny task do wysyłania klatek
        self.sender_task = asyncio.create_task(self.send_frames())

    def read_camera(self, loop):
        self.cap = cv2.VideoCapture(0)  # Kamera domyślna (0)

        # Mierzenie FPS
        frame_count = 0
        start_time = time.time()
        fps_interval = 1.0        # Liczenie co sekunde

        try:
            while self.running:
                # Odczyt klatki z kamery
                ret, frame = self.cap.read()
                if not ret:
                    # Jeśli brak klatki - break
                    break

                # Liczenie klatek
                frame_count += 1
                # Obliczamy czas, który minął od ostatniego "resetu"
                elapsed = time.time() - start_time
                if elapsed >= fps_interval:
                    # FPS - liczba klatek / czas
                    fps = frame_count / elapsed
                    print(f"[Camera] FPS: {fps:.2f}")
                    # Reset licznika i czasu
                    frame_count = 0
                    start_time = time.time()

                frame = cv2.flip(frame, 1)  # Odbicie lustrzane
                # Kodowanie do jpg - może da się to lepiej rozwiązać
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])  # 80% jakości
                # Konwersja tab. numpy na bajty - do przesyłu.
                frame_bytes = buffer.tobytes()
                # Wrzucenie klatki do kolejki asynch.
                asyncio.run_coroutine_threadsafe(self.queue.put(frame_bytes), loop)
        finally:
            # Zawsze się wykona, wyjątek lub przerwanie też się zalicza
            if self.cap is not None:
                self.cap.release()  # Zwolnienie kam.
                print("Camera has been released (read_camera).")

    async def send_frames(self):
        while self.running:
            try:
                # Pobieranie klatki z kolejki - asynch.
                frame_bytes = await asyncio.wait_for(self.queue.get(), timeout=1.0)  # Czekanie sekunde
                # Wysłanie klatki
                await self.send(bytes_data=frame_bytes)
            except asyncio.TimeoutError:
                # Jeśli nic nie przyszło do kolejki w ciągu 1 sekundy - skip
                pass
            except asyncio.CancelledError:
                # Wyjątek rzucany przy cancelowaniu taska
                break

    async def disconnect(self, close_code):
        self.running = False  # Flaga na false - żeby wyłączyć kam.
        # Cancel task wysyłający klatki, jeśli istnieje
        if self.sender_task:
            self.sender_task.cancel()
        # zwolnienie zasobów
        await self.shutdown()

        # StopConsumer - django channels kończy działanie tego consumera
        raise StopConsumer()

    async def shutdown(self):
        # Zwolnienie kam. gdyby read_camera jeszcze jej nie zwolniło.
        if self.cap is not None:
            self.cap.release()
            print("Camera manually released in shutdown.")

        # Wyłączenie executora - wait=False zapobiega blokowaniu event loop.
        self.executor.shutdown(wait=False)
        print("Camera stream disconnected")


class ScreenStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        # Przekazanie wszystkich argumentów pozycyjnych i słownikowych do konstruktora rodzica
        # Czyli żeby mogło korzystać z AsyncWebsocketConsumer z django channels
        super().__init__(*args, **kwargs)
        self.executor = ThreadPoolExecutor(max_workers=1)  # 1 Wątek dla kamery
        self.queue = Queue()  # Kolejka asynchroniczna na klatki obrazu ekranu
        self.running = False  # Flaga informująca o działaniu

        # Taski asynchroniczne
        self.screen_task = None  # Zadanie w wątku do przechwytywania ekranu
        self.sender_task = None  # Zadanie do wysyłania klatek do klienta

    async def connect(self):
        await self.accept()  # Połączenie WebSocket
        self.running = True  # Flaga true - pętla działa

        loop = asyncio.get_event_loop()
        # Uruchomienie capture_screen w wątku
        self.screen_task = loop.run_in_executor(self.executor, self.capture_screen, loop)
        # Asynchroniczny task do wysyłania klatek
        self.sender_task = asyncio.create_task(self.send_frames())

    def capture_screen(self, loop):
        try:
            while self.running:
                # Pobranie zrzutu ekranu
                screenshot = pyautogui.screenshot()
                # Konwersja z RGB do BGR (OpenCV standard)
                frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                # Kodowanie do jpg - może da się to lepiej rozwiązać
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])  # 70% jakości
                # Konwersja tab. numpy na bajty - do przesyłu.
                frame_bytes = buffer.tobytes()
                # Wrzucenie klatki do kolejki asynch.
                asyncio.run_coroutine_threadsafe(self.queue.put(frame_bytes), loop)
        finally:
            # Zawsze się wykona, wyjątek lub przerwanie też się zalicza
            print("Screen capture stopped.")

    async def send_frames(self):
        while self.running:
            try:
                # Pobieranie klatki z kolejki - asynch.
                frame_bytes = await asyncio.wait_for(self.queue.get(), timeout=1.0)  # Czekanie sekunde
                # Wysłanie klatki
                await self.send(bytes_data=frame_bytes)
            except asyncio.TimeoutError:
                # Jeśli brak klatek - pass
                pass
            except asyncio.CancelledError:
                # Anulowanie taska przy rozłączeniu
                break

    async def disconnect(self, close_code):
        # Flaga na false
        self.running = False
        # Anulowanie pętli wysyłającej, jeśli aktywna
        if self.sender_task:
            self.sender_task.cancel()
        # Zwolnienie zasobów
        await self.shutdown()
        # StopConsumer - django channels kończy działanie tego consumera
        raise StopConsumer()

    async def shutdown(self):
        # Wyłączenie executora - wait=False zapobiega blokowaniu event loop.
        self.executor.shutdown(wait=False)
        print("Screen stream disconnected.")
