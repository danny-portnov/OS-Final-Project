#!/usr/bin/env python
from multiprocessing import Process, JoinableQueue, Lock, Queue
from threading import Thread
import time
import os
import numpy as np

file_lock = Lock()

# reading wires from file so each thread reads one line at a given time (with file_lock for sync)


def InitMatricesAndCalResistance(fileQ, wires_q, verticalMatrix, hortizontalMatrix):
    while True:
        x_vector = []
        y_vector = []
        wire_r = 0
        # fields - "(0,20),(20,20),(20,48),(48,48),(48,32)" for example
        wire_name, fields = fileQ.get()
        # vector - ["0,20","20,20","20,48","48,48","48,32"] for example
        vector = fields[1:-1].split('),(')
        for v in vector:
            x, y = v.split(',')
            x_vector.append(int(x))
            y_vector.append(int(y))

        for i in range(1, len(x_vector)):
            wire_r += abs(x_vector[i] - x_vector[i-1]) + \
                abs(y_vector[i] - y_vector[i-1])

            # horizontal line
            if (y_vector[i] == y_vector[i-1]):
                min_x = min(x_vector[i], x_vector[i-1])
                max_x = max(x_vector[i], x_vector[i-1])
                # inserting 1's in (L x 1) segment
                for column in range(min_x, max_x):
                    hortizontalMatrix[y_vector[i]][column] = 1

            # vertical line
            else:
                min_y = min(y_vector[i], y_vector[i-1])
                max_y = max(y_vector[i], y_vector[i-1])
                # inserting 1's in (1 x L) segment
                for row in range(min_y, max_y):
                    verticalMatrix[row][x_vector[i]] = 1

        wires_q.put((wire_name, wire_r, (x_vector, y_vector)))
        fileQ.task_done()
        print(f"Wire {wire_name} calculated")


def read_wire(file_handler, fileQ):
    for line in file_handler:
        fileQ.put(line.strip().split())
    print("Finished reading from file")


# calculating capacitance of wires with threads so each thread works on one wire
# at a given time


def calc_cap(wires_q: JoinableQueue, results_q, verticalMatrix, hortizontalMatrix):
    # The x dimension of the matrix is the length of some row
    size_x = len(verticalMatrix[0])
    # The y dimension of the matrix is the amount of rows
    size_y = len(verticalMatrix)
    while True:
        try:
            wire = wires_q.get(timeout=15)
            if wire == 'END':
                return
            print(f"Got wire {wire[0]}'s for capacitance")
        except:
            print("Timeout")
            break
        cap = 0
        wire_name = wire[0]
        wire_res = wire[1]
        x = wire[2][0]
        y = wire[2][1]
        for i in range(1, len(x)):
            # check for line type - horizontal or vertical
            vertical = x[i] == x[i-1]
            min_x = min(x[i], x[i-1])
            max_x = max(x[i], x[i-1])
            min_y = min(y[i], y[i-1])
            max_y = max(y[i], y[i-1])
            if vertical:
                # summing capacity 4 columns to the left and right of the vertical line
                for column in range(max(0, min_x-4), min(min_x+5, size_x)):
                    # Skip the column of the current wire
                    if column == min_x:
                        continue
                    for row in range(min_y, max_y):
                        cap += verticalMatrix[row][column]
            else:
                # summing capacity 4 rows to the top and bottom of the horizontal line
                for row in range(max(0, min_y-4), min(min_y+5, size_y)):
                    # Skip the row of the current wire
                    if row == min_y:
                        continue
                    for column in range(min_x, max_x):
                        cap += hortizontalMatrix[row][column]

        results_q.put((wire_name, wire_res, cap))
        print(f"Wire {wire_name}'s capacitance calculated")

# writing to file the resistance and capacitance of each wire


def write_to_file(filename, results_q):
    # adding or converting existing extension to .res
    fields = filename.split('.')
    if len(fields) >= 2:
        fields[-1] = 'res'
        outfile = '.'.join(fields)
    else:
        outfile = filename + '.res'

    results = []
    while True:
        item = results_q.get()
        if item == 'END':
            break
        results.append(item)

    print("Writing results to file...")
    # alphabetic sorting
    results.sort(key=lambda x: x[0])

    with open(outfile, 'w') as fw:
        for res in results:
            fw.write(
                f"{res[0].ljust(20)} {str(res[1]).ljust(8)} {str(res[2]).ljust(8)}\n")
    print(f"{len(results)} wires calculated and exported to {outfile}")


def main():
    # cpu_num = int(input("Enter the number of CPUs to use: "))
    cpu_num = 2  # For debug
    files = [f for f in os.listdir(os.path.join(
        os.getcwd(), 'working_circuits_0104')) if f.endswith('.dat')]
    start = time.time()

    for filename in files:
        if filename != "cir1000.dat":
            continue
        processes = []
        wires_q = Queue()
        results_q = Queue()
        fileQ = JoinableQueue()
        filePath = os.path.join(os.getcwd(), 'working_circuits_0104', filename)
        with open(filePath) as f:
            lines = f.readlines()
            print(f"File {filename} loaded successfully")
            _, x_size, y_size = lines.pop(0).strip().split()
            # 2 matrices with (x_size x y_size) shape for sharing between threads
            # one is for horizontal lines and the other is for vertical lines
            # we'll use them for calculating the capacitance of each wire

            verticalMatrix = [[0 for _ in range(int(y_size))]
                              for _ in range(int(x_size))]
            hortizontalMatrix = [[0 for _ in range(int(y_size))]
                                 for _ in range(int(x_size))]
            print("Reading wires from file...")
            readProcess = Process(target=read_wire, args=(lines, fileQ))
            readProcess.start()  # todo: if terminate is not needed, do it one line
            processes = []
            for _ in range(cpu_num):
                p = Process(target=InitMatricesAndCalResistance, args=(
                    fileQ, wires_q, verticalMatrix, hortizontalMatrix))
                p.start()
                processes.append(p)
            fileQ.join()
            for p in processes:
                p.terminate()
                wires_q.put("END")
            readProcess.terminate()
            print("Calculating capacitance...")
            processes = []
    # num_wires = wires_q.qsize()
            for _ in range(cpu_num):
                p = Process(target=calc_cap, args=(
                    wires_q, results_q, verticalMatrix, hortizontalMatrix))
                p.start()
                processes.append(p)
            resultsProcess = Process(target=write_to_file,
                                     args=(filename, results_q))
            resultsProcess.start()
            for p in processes:
                p.join()
            results_q.put("END")
            print("Finished calculating capacitance")
            for p in processes:
                p.terminate()

            resultsProcess.join()
    print("in ", time.time() - start, " seconds")


if __name__ == '__main__':
    main()
