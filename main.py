#!/usr/bin/env python
from multiprocessing import JoinableQueue, Queue
from threading import Thread
import time
import os


def InitMatricesAndCalResistance(fileQ, wiresQ, verticalMatrix, hortizontalMatrix):
    # reading wires from file so each thread reads one line at a given time
    while True:
        xVector = []
        yVector = []
        wireResistance = 0
        item = fileQ.get()
        if item == 'END':
            return
        # fields - "(0,20),(20,20),(20,48),(48,48),(48,32)" for example
        wire_name, fields = item
        # vector - ["0,20","20,20","20,48","48,48","48,32"] for example
        vector = fields[1:-1].split('),(')
        for v in vector:
            x, y = v.split(',')
            xVector.append(int(x))
            yVector.append(int(y))

        for i in range(1, len(xVector)):
            wireResistance += abs(xVector[i] - xVector[i-1]) + \
                abs(yVector[i] - yVector[i-1])

            # horizontal line
            if yVector[i] == yVector[i-1]:
                min_x = min(xVector[i], xVector[i-1])
                max_x = max(xVector[i], xVector[i-1])
                # inserting 1's in (L x 1) segment
                for column in range(min_x, max_x):
                    hortizontalMatrix[yVector[i]][column] = 1

            # vertical line
            else:
                min_y = min(yVector[i], yVector[i-1])
                max_y = max(yVector[i], yVector[i-1])
                # inserting 1's in (1 x L) segment
                for row in range(min_y, max_y):
                    verticalMatrix[row][xVector[i]] = 1

        wiresQ.put((wire_name, wireResistance, (xVector, yVector)))
        fileQ.task_done()


def ReadFromWiresFile(file_handler, fileQ):
    for line in file_handler:
        fileQ.put(line.strip().split())
    print("Finished reading from file")


def CalculateCapacitance(wiresQ: JoinableQueue, resultsQ, verticalMatrix, hortizontalMatrix):
    # calculating capacitance of wires with threads so each thread works on one wire
    # at a given time
    # The x dimension of the matrix is the length of some row
    # (which is the amount of columns)
    amountOfColumns = len(verticalMatrix[0])
    # The y dimension of the matrix is the amount of rows
    amountOfRows = len(verticalMatrix)
    while True:
        wire = wiresQ.get()
        if wire == 'END':
            return
        capacitance = 0
        wireName = wire[0]
        wireResistance = wire[1]
        x = wire[2][0]
        y = wire[2][1]
        for i in range(1, len(x)):
            # check for line type - horizontal or vertical
            vertical = x[i] == x[i-1]
            minX = min(x[i], x[i-1])
            maxX = max(x[i], x[i-1])
            minY = min(y[i], y[i-1])
            maxY = max(y[i], y[i-1])
            if vertical:
                # summing capacity 4 columns to the left and right of the vertical line
                for column in range(max(0, minX-4), min(minX+5, amountOfColumns)):
                    # Skip the column of the current wire
                    if column == minX:
                        continue
                    for row in range(minY, maxY):
                        capacitance += verticalMatrix[row][column]
            else:
                # summing capacity 4 rows to the top and bottom of the horizontal line
                for row in range(max(0, minY-4), min(minY+5, amountOfRows)):
                    # Skip the row of the current wire
                    if row == minY:
                        continue
                    for column in range(minX, maxX):
                        capacitance += hortizontalMatrix[row][column]

        resultsQ.put((wireName, wireResistance, capacitance))
        # print(f"Wire {wire_name}'s capacitance calculated")


def SaveResultsToFile(fileName: str, resultsQ):
    # writing to file the resistance and capacitance of each wire
    results = []
    while True:
        item = resultsQ.get()
        if item == 'END':
            break
        results.append(item)

    print("Writing results to file...")
    # Natural sorting
    # Assuming the wire name always starts with "net"
    results.sort(key=lambda x: int(x[0][3:]))

    # The file ends with ".dat"
    outfile = fileName.replace("dat", "res")
    with open(outfile, 'w') as fw:
        for wireName, resistance, capacitance in results:
            fw.write(f"{wireName:<20} {resistance:<8} {capacitance:<8}\n")
    print(f"{len(results)} wires calculated and exported to {outfile}")


def main():
    numberOfThreads = int(input("Enter the number of threads to use: "))
    # numberOfThreads = 2  # For debug
    directoryToProcess = os.path.join(os.getcwd(), 'working_circuits_0104')
    # Taking only files that end with ".dat"
    files = [f for f in os.listdir(directoryToProcess) if f.endswith('.dat')]
    start = time.time()

    for filename in files:
        threads = []
        wiresQ = Queue()
        resultsQ = Queue()
        fileQ = JoinableQueue()
        filePath = os.path.join(directoryToProcess, filename)
        with open(filePath) as f:
            lines = f.readlines()
        print(f"File {filename} loaded successfully")
        _, xSize, ySize = lines.pop(0).strip().split()
        # Start to read the file before builiding the matrices, as it takes time
        print("Reading wires from file...")
        readThread = Thread(target=ReadFromWiresFile, args=(lines, fileQ))
        readThread.start()
        # 2 matrices with (xSize x ySize) shape for sharing between threads
        # one is for horizontal lines and the other is for vertical lines
        # we'll use them for calculating the capacitance of each wire
        print("Building matrices...")
        verticalMatrix = [[0 for _ in range(int(ySize))]
                          for _ in range(int(xSize))]
        hortizontalMatrix = [
            [0 for _ in range(int(ySize))] for _ in range(int(xSize))]
        print("Finished building matrices")
        threads = []
        for _ in range(numberOfThreads):
            t = Thread(target=InitMatricesAndCalResistance, args=(
                fileQ, wiresQ, verticalMatrix, hortizontalMatrix))
            t.start()
            threads.append(t)
        readThread.join()
        fileQ.join()
        for t in threads:  # All data was read from file, signal the threads to end
            fileQ.put("END")
        print("Calculating capacitance...")
        threads = []
        for _ in range(numberOfThreads):
            t = Thread(target=CalculateCapacitance, args=(
                wiresQ, resultsQ, verticalMatrix, hortizontalMatrix))
            t.start()
            threads.append(t)
        resultsThread = Thread(target=SaveResultsToFile,
                               args=(filename, resultsQ))
        resultsThread.start()
        for t in threads:  # Signal capacitance threads to end
            wiresQ.put("END")
        for t in threads:  # Wait for threads to end
            t.join()
        resultsQ.put("END")
        print("Finished calculating capacitance")

        resultsThread.join()
        print(
            f"Finished processing file: {filename} in {(time.time() - start)} seconds")
        print()
    print(f"Finished processing all files in {(time.time() - start)} seconds")


if __name__ == '__main__':
    main()
