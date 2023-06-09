from Enum.EnumInstruction import EInstruction
from Enum.EnumDirection import EDirection
from Enum.EnumVehicle import EVehicleType
from Enum.EnumSignal import ESignal
from Enum.EnumMode import EMode

from POJO.Intersection.Road import Road
from POJO.Communication import Communication

from Model.WebSocket import WebSocket

from threading import Thread
import pygame
import random
import json
import time
import sys
import os


class Main:
    def __init__(self, name, limitTime):
        pygame.init()
        pygame.display.set_caption(name)

        # Settings / 設定
        # Setup Primary Roads Period / 設定主要道路的紅黃綠燈週期
        self.defaultPrimaryTrafficPeriod = {
            ESignal.GREEN.name: 40,
            ESignal.GREEN.YELLOW.name: 5,
            ESignal.RED.name: 15
        }
        # Setup Second Roads Period / 設定次要道路的紅黃綠燈週期
        self.defaultSecondTrafficPeriod = {
            ESignal.GREEN.name: 15,
            ESignal.GREEN.YELLOW.name: 5,
            ESignal.RED.name: 40
        }
        # Generate vehicle's period (per second) / 產生車輛的週期 (台/秒)
        self.generatePeriod = 1
        # Setup Default Traffic Mode / 設定初始道路狀態
        self.mode = EMode.NORMAL
        # Setup Traffic Jam Direction / 設定堵塞的道路
        self.trafficJamDirection = [EDirection.NORTH, EDirection.SOUTH]
        # Setup Traffic Jam Period / 設定堵塞道路的紅黃綠燈週期
        self.trafficJamPeriod = {
            ESignal.GREEN.name: 20,
            ESignal.GREEN.YELLOW.name: 5,
            ESignal.RED.name: 35
        }
        # Setup Non-Traffic Jam Period / 設定非堵塞道路的紅黃綠燈週期
        self.nonTrafficJamPeriod = {
            ESignal.GREEN.name: 35,
            ESignal.GREEN.YELLOW.name: 5,
            ESignal.RED.name: 20
        }

        # Setup which traffic is primary / 設定哪條道路是主要道路
        # primary usually have more time / 主要道路通常有比較多的時間
        roadEast = Road(EDirection.EAST, isPrimary=True)
        roadWest = Road(EDirection.WEST, isPrimary=True)
        roadSouth = Road(EDirection.SOUTH, isPrimary=False)
        roadNorth = Road(EDirection.NORTH, isPrimary=False)

        # Setup Default Traffic Mode / 設定初始道路紅綠燈的訊號
        roadEast.trafficSignals.setSignal(ESignal.GREEN)
        roadWest.trafficSignals.setSignal(ESignal.GREEN)

        roadSouth.trafficSignals.setSignal(ESignal.RED)
        roadNorth.trafficSignals.setSignal(ESignal.RED)

        # Load in Array / 載入陣列
        self.roads = {
            EDirection.EAST.name: roadEast,
            EDirection.WEST.name: roadWest,
            EDirection.SOUTH.name: roadSouth,
            EDirection.NORTH.name: roadNorth,
        }

        # Setup Primary.Second traffic and default Period / 設定 主要.次要道路週期以及預設週期
        for (key, road) in self.roads.items():
            if road.isPrimary:
                road.defaultPeriod = self.defaultPrimaryTrafficPeriod.copy()
                road.trafficSignals.signalStates = self.defaultPrimaryTrafficPeriod.copy()
            else:
                road.defaultPeriod = self.defaultSecondTrafficPeriod.copy()
                road.trafficSignals.signalStates = self.defaultSecondTrafficPeriod.copy()

        # Pygame objects
        self.simulation = pygame.sprite.Group()

        # Screensize
        screenWidth = 1400
        screenHeight = 800
        self.screenSize = (screenWidth, screenHeight)

        # Coordinates of vehicle count counter
        self.vehicleCountTexts = ["0", "0", "0", "0"]
        self.vehicleCountCoordinates = [(480, 210), (880, 210), (880, 550), (480, 550)]

        # Coordinates of signal image, timer
        self.signalTexts = ["", "", "", ""]
        self.signalCoordinates = [(530, 230), (810, 230), (810, 570), (530, 570)]
        self.signalTimerCoordinates = [(530, 210), (810, 210), (810, 550), (530, 550)]

        # Coordinates of stop lines
        self.stopLines = {
            EDirection.EAST: 590,
            EDirection.WEST: 800,
            EDirection.NORTH: 330,
            EDirection.SOUTH: 535
        }
        self.stopPosition = {
            EDirection.EAST: 580,
            EDirection.WEST: 810,
            EDirection.NORTH: 320,
            EDirection.SOUTH: 545
        }
        self.vehiclesNotTurned = {
            EDirection.EAST: {1: [], 2: []},
            EDirection.WEST: {1: [], 2: []},
            EDirection.NORTH: {1: [], 2: []},
            EDirection.SOUTH: {1: [], 2: []}
        }

        # Display time elapsed
        self.timeElapsed = 0
        self.simulationTime = limitTime
        self.timeElapsedCoordinate = (1100, 50)
        # Colours
        self.black = (0, 0, 0)
        self.white = (255, 255, 255)
        # Font
        self.font = pygame.font.Font(None, 30)

        # Gap between vehicles
        self.stoppingGap = 25
        self.movingGap = 25

        t = Thread(target=self.generatorVehicle)
        t.start()

        t = Thread(target=self.countTime)
        t.start()

        t = Thread(target=self.countSignalTime)
        t.start()

        self.ws = WebSocket(self.wsReceiveHandler)
        self.ws.run()

    def run(self):
        # Load images
        backgroundImage = pygame.image.load("Data/Images/intersection.png")
        greenSignal = pygame.image.load("Data/Images/Signals/GREEN.PNG")
        yellowSignal = pygame.image.load("Data/Images/Signals/YELLOW.PNG")
        redSignal = pygame.image.load("Data/Images/Signals/RED.PNG")

        # Load image into array
        signalImages = {
            ESignal.GREEN.name: greenSignal,
            ESignal.YELLOW.name: yellowSignal,
            ESignal.RED.name: redSignal
        }

        screen = pygame.display.set_mode(self.screenSize)

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            # Display background in simulation
            screen.blit(backgroundImage, (0, 0))

            # Display time elapsed
            timeElapsedText = self.font.render(f"Time Elapsed:  {self.timeElapsed}", True, self.black, self.white)
            screen.blit(timeElapsedText, self.timeElapsedCoordinate)

            # Display signal and set timer according to current status: green, yellow, or red
            for index, (key, road) in enumerate(self.roads.items()):
                screen.blit(signalImages[road.trafficSignals.currentSignal.name], self.signalCoordinates[index])

            # Display signal timer
            for index, (key, road) in enumerate(self.roads.items()):
                signalTime = road.trafficSignals.signalStates[road.trafficSignals.currentSignal.name]
                self.signalTexts[index] = self.font.render(str(signalTime), True, self.white, self.black)
                screen.blit(self.signalTexts[index], self.signalTimerCoordinates[index])

            # Display vehicle count
            for index, (key, road) in enumerate(self.roads.items()):
                displayText = road.crossed
                self.vehicleCountTexts[index] = self.font.render(str(displayText), True, self.black, self.white)
                screen.blit(self.vehicleCountTexts[index], self.vehicleCountCoordinates[index])

            # Display the vehicles
            for vehicle in self.simulation:
                screen.blit(vehicle.image, [vehicle.x, vehicle.y])
                self.move(vehicle)
            pygame.display.update()

    def generatorVehicle(self):
        # Generating vehicles in the simulation
        while True:
            direction = random.choice(list(EDirection))
            road = self.roads[direction.name]
            EVehicle = random.choice(list(EVehicleType))
            vehicle = VehicleObject(EVehicle, direction)
            road.lane[vehicle.lane].append(vehicle)
            vehicle.index = len(road.lane[vehicle.lane]) - 1

            preVehicle = road.lane[vehicle.lane][vehicle.index - 1]
            if len(road.lane[vehicle.lane]) > 1 and preVehicle.crossed == 0:
                if direction == EDirection.EAST:
                    vehicle.stop = preVehicle.stop - preVehicle.image.get_rect().width - self.stoppingGap
                elif direction == EDirection.WEST:
                    vehicle.stop = preVehicle.stop + preVehicle.image.get_rect().width + self.stoppingGap
                elif direction == EDirection.NORTH:
                    vehicle.stop = preVehicle.stop - preVehicle.image.get_rect().height - self.stoppingGap
                elif direction == EDirection.SOUTH:
                    vehicle.stop = preVehicle.stop + preVehicle.image.get_rect().height + self.stoppingGap
            else:
                vehicle.stop = self.stopPosition[direction]

            # Set new starting and stopping coordinate
            if direction == EDirection.EAST:
                temp = vehicle.image.get_rect().width + self.stoppingGap
                vehicle.x -= temp
            elif direction == EDirection.WEST:
                temp = vehicle.image.get_rect().width + self.stoppingGap
                vehicle.x += temp
            elif direction == EDirection.NORTH:
                temp = vehicle.image.get_rect().height + self.stoppingGap
                vehicle.y -= temp
            elif direction == EDirection.SOUTH:
                temp = vehicle.image.get_rect().height + self.stoppingGap
                vehicle.y += temp

            self.simulation.add(vehicle)

            time.sleep(self.generatePeriod)

    def showStats(self):
        totalVehicles = 0
        print("\nDirection-wise Vehicle Counts")

        for (key, road) in self.roads.items():
            print(f"Direction: {road.direction} : {road.crossed}")
            totalVehicles += road.crossed

        print(f"Total vehicles passed: {totalVehicles}")
        print(f"Total time: {self.timeElapsed}\n")

    def countTime(self):
        while True:
            self.timeElapsed += 1
            time.sleep(1)
            if self.timeElapsed == self.simulationTime:
                self.showStats()
                os._exit(1)

    def countSignalTime(self):
        while True:
            while self.mode == EMode.NORMAL:
                for index, (key, road) in enumerate(self.roads.items()):
                    currentSignal = road.trafficSignals.currentSignal
                    signalTime = road.trafficSignals.signalStates[currentSignal.name]
                    if signalTime > 0:
                        road.trafficSignals.signalStates[currentSignal.name] -= 1
                    else:
                        road.trafficSignals.switchNextSignal()
                        if road.direction == EDirection.EAST or road.direction == EDirection.WEST:
                            road.trafficSignals.signalStates = self.defaultPrimaryTrafficPeriod.copy()
                        else:
                            road.trafficSignals.signalStates = self.defaultSecondTrafficPeriod.copy()
                    if self.mode is not EMode.NORMAL and currentSignal == ESignal.YELLOW:
                        break
                time.sleep(1)

            while self.mode == EMode.TRAFFIC_JAM:
                for index, (key, road) in enumerate(self.roads.items()):
                    currentSignal = road.trafficSignals.currentSignal
                    signalTime = road.trafficSignals.signalStates[currentSignal.name]
                    if signalTime > 0:
                        road.trafficSignals.signalStates[currentSignal.name] -= 1
                    else:
                        road.trafficSignals.switchNextSignal()
                        if road.direction in self.trafficJamDirection:
                            road.trafficSignals.signalStates = self.trafficJamPeriod.copy()
                        else:
                            road.trafficSignals.signalStates = self.nonTrafficJamPeriod.copy()
                    if self.mode is not EMode.TRAFFIC_JAM and currentSignal == ESignal.YELLOW:
                        break
                time.sleep(1)

            while self.mode == EMode.EMERGENCY:
                pass

            time.sleep(1)

    def move(self, vehicle):
        if vehicle.direction == EDirection.EAST:
            if vehicle.crossed == 0 and vehicle.x + vehicle.image.get_rect().width > self.stopLines[vehicle.direction]:
                vehicle.crossed = 1
                self.roads[vehicle.direction.name].crossed += 1
                self.vehiclesNotTurned[vehicle.direction][vehicle.lane].append(vehicle)
                vehicle.crossedIndex = len(self.vehiclesNotTurned[vehicle.direction][vehicle.lane]) - 1
            if vehicle.crossed == 0:
                preVehicle = self.roads[vehicle.direction.name].lane[vehicle.lane][vehicle.index - 1]
                if ((vehicle.x + vehicle.image.get_rect().width <= vehicle.stop or (
                        self.roads[vehicle.direction.name].trafficSignals.currentSignal == ESignal.GREEN)) and (
                        vehicle.index == 0 or vehicle.x + vehicle.image.get_rect().width < (
                        preVehicle.x - self.movingGap))):
                    vehicle.x += vehicle.speed
            else:
                if ((vehicle.crossedIndex == 0) or (vehicle.x + vehicle.image.get_rect().width < (
                        self.vehiclesNotTurned[vehicle.direction][vehicle.lane][vehicle.crossedIndex - 1].x - self.movingGap))):
                    vehicle.x += vehicle.speed

        elif vehicle.direction == EDirection.NORTH:
            if vehicle.crossed == 0 and vehicle.y + vehicle.image.get_rect().height > self.stopLines[vehicle.direction]:
                vehicle.crossed = 1
                self.roads[vehicle.direction.name].crossed += 1
                self.vehiclesNotTurned[vehicle.direction][vehicle.lane].append(vehicle)
                vehicle.crossedIndex = len(self.vehiclesNotTurned[vehicle.direction][vehicle.lane]) - 1
            if vehicle.crossed == 0:
                preVehicle = self.roads[vehicle.direction.name].lane[vehicle.lane][vehicle.index - 1]
                if ((vehicle.y + vehicle.image.get_rect().height <= vehicle.stop or (
                        self.roads[vehicle.direction.name].trafficSignals.currentSignal == ESignal.GREEN)) and (
                        vehicle.index == 0 or vehicle.y + vehicle.image.get_rect().height < (
                        preVehicle.y - self.movingGap))):
                    vehicle.y += vehicle.speed
            else:
                if ((vehicle.crossedIndex == 0) or (vehicle.y + vehicle.image.get_rect().height < (
                        self.vehiclesNotTurned[vehicle.direction][vehicle.lane][vehicle.crossedIndex - 1].y - self.movingGap))):
                    vehicle.y += vehicle.speed

        elif vehicle.direction == EDirection.WEST:
            if vehicle.crossed == 0 and vehicle.x < self.stopLines[vehicle.direction]:
                vehicle.crossed = 1
                self.roads[vehicle.direction.name].crossed += 1
                self.vehiclesNotTurned[vehicle.direction][vehicle.lane].append(vehicle)
                vehicle.crossedIndex = len(self.vehiclesNotTurned[vehicle.direction][vehicle.lane]) - 1
            if vehicle.crossed == 0:
                preVehicle = self.roads[vehicle.direction.name].lane[vehicle.lane][vehicle.index - 1]
                if ((vehicle.x >= vehicle.stop or (
                        self.roads[vehicle.direction.name].trafficSignals.currentSignal == ESignal.GREEN)) and (
                        vehicle.index == 0 or vehicle.x > (
                        preVehicle.x + preVehicle.image.get_rect().width + self.movingGap))):
                    vehicle.x -= vehicle.speed
            else:
                preVehicleNT = self.vehiclesNotTurned[vehicle.direction][vehicle.lane][vehicle.crossedIndex - 1]
                if ((vehicle.crossedIndex == 0) or (vehicle.x > (
                        preVehicleNT.x + preVehicleNT.image.get_rect().width + self.movingGap))):
                    vehicle.x -= vehicle.speed

        elif vehicle.direction == EDirection.SOUTH:
            if vehicle.crossed == 0 and vehicle.y < self.stopLines[vehicle.direction]:
                vehicle.crossed = 1
                self.roads[vehicle.direction.name].crossed += 1
                self.vehiclesNotTurned[vehicle.direction][vehicle.lane].append(vehicle)
                vehicle.crossedIndex = len(self.vehiclesNotTurned[vehicle.direction][vehicle.lane]) - 1
            if vehicle.crossed == 0:
                preVehicle = self.roads[vehicle.direction.name].lane[vehicle.lane][vehicle.index - 1]
                if ((vehicle.y >= vehicle.stop or (
                        self.roads[vehicle.direction.name].trafficSignals.currentSignal == ESignal.GREEN)) and (
                        vehicle.index == 0 or vehicle.y > (
                        preVehicle.y + preVehicle.image.get_rect().height + self.movingGap))):
                    vehicle.y -= vehicle.speed
            else:
                preVehicleNT = self.vehiclesNotTurned[vehicle.direction][vehicle.lane][vehicle.crossedIndex - 1]
                if ((vehicle.crossedIndex == 0) or (vehicle.y > (
                        preVehicleNT.y + preVehicleNT.image.get_rect().height + self.movingGap))):
                    vehicle.y -= vehicle.speed

    def wsReceiveHandler(self, msg):
        jsonData = json.loads(msg)
        instruction = jsonData["instruction"]
        if instruction == EInstruction.REQUIRE_DATA_CURRENT_TRAFFIC_STATE.name:
            data = {}
            for (key, road) in self.roads.items():
                data[key] = road.trafficSignals.currentSignal.name
            self.wsSend(Communication(EInstruction.SEND_DATA_CURRENT_TRAFFIC_STATE.name, data).toJson())
        elif instruction == EInstruction.REQUIRE_DATA_TRAFFIC_PERIOD.name:
            data = {}
            for (key, road) in self.roads.items():
                data[key] = road.defaultPeriod
            self.wsSend(Communication(EInstruction.SEND_DATA_TRAFFIC_PERIOD.name, data).toJson())
        elif instruction == EInstruction.SWITCH_MODE.name:
            pass

    def wsSend(self, data):
        self.ws.server.send_message_to_all(data)


class VehicleObject(pygame.sprite.Sprite):
    def __init__(self, EVehicle, direction):
        super().__init__()

        # Coordinates of vehicles start
        xAxis = {
            EDirection.EAST: [0, 0, 0],
            EDirection.WEST: [1400, 1400, 1400],
            EDirection.NORTH: [755, 727, 697],
            EDirection.SOUTH: [602, 627, 657]
        }
        yAxis = {
            EDirection.EAST: [348, 370, 398],
            EDirection.WEST: [498, 466, 436],
            EDirection.NORTH: [0, 0, 0],
            EDirection.SOUTH: [800, 800, 800]
        }

        self.lane = random.randint(1, 2)
        self.speed = EVehicle.speed
        self.direction = direction
        self.crossedIndex = 0
        self.crossed = 0
        self.index = None
        self.stop = None
        self.x = xAxis[direction][self.lane]
        self.y = yAxis[direction][self.lane]

        imagePath = f"Data/Images/{direction.name}/{EVehicle.vType}.png"
        self.image = pygame.image.load(imagePath)


if __name__ == "__main__":
    obj = Main("Intersection Simulation", 9999)
    obj.run()
