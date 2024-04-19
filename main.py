#! /usr / env python

import os
import sys
import re
from multiprocessing import Process, Queue, JoinableQueue
from typing import List, Tuple


def calc_resistance(in_q: Queue, out_q: Queue) -> None:
    while True:
        tot_res = 0
        # data[0] = cordinations of the wire
        data: Tuple[List[str], int] = in_q.get()
        # data[1] = wire's index
        wire: List[str] = data[0]
        for idx in range(len(wire)-1):
            cord1 = [int(x) for x in wire[idx].split(',')]
            cord2 = [int(x) for x in wire[idx].split(',')]

            dif_x = abs(cord1[0] - cord2[0])  # |(X1-X2)|
            dif_y = abs(cord1[1] - cord2[1])  # |(y1-y1)|
            if (dif_x == 0):  # Vertical segment
                tot_res += dif_y

            elif (dif_y == 0):  # Horizontal segment
                tot_res += dif_x

        output_data = [tot_res, data[1]]
        # transfer (calculated resistance, wire's index ) to MAIN
        out_q.put(output_data)


def nets2chip(chip_arr: List[List[tuple[str, int]]], c_in_q: Queue, c_out_q: Queue) -> None:
    while True:
        net: tuple[int, list[str]] = c_in_q.get()
        if net == "END":
            break
        net_idx = net[0]
        cords = net[1]
        for i in range(len(cords)-1):
            cord1 = cords[i].split(',')
            cord2 = cords[i+1].split(',')
            x1, y1 = int(cord1[0]), int(cord1[1])
            x2, y2 = int(cord2[0]), int(cord2[1])
            dif_x = x1 - x2  # |(X1-X2)|
            dif_y = y1 - y2  # |(y1-y1)|

        # Vertical segment
            if (dif_x == 0):
                if dif_y < 0:
                    for idx in range(y1, y2):
                        chip_arr[x1][idx] = ("V", net_idx)

                elif dif_y > 0:
                    for idx in range(y1, y2, -1):
                        chip_arr[x1][idx] = ("V", net_idx)

            elif (dif_y == 0):
                if dif_x < 0:
                    for idx in range(x1, x2):
                        chip_arr[idx][y1] = ("H", net_idx)

                elif dif_x > 0:
                    for idx in range(x1, x2, -1):
                        chip_arr[idx][y1] = ("H", net_idx)
    c_out_q.put(chip_arr)


def calc_capacitance(chip_arr: List[List[str]], cap_in_q: JoinableQueue, cap_out_q: JoinableQueue) -> None:
    while True:
        cord = cap_in_q.get()
        x_idx, y_idx = cord[0], cord[1]
        wire = 0
        add = 0
    # -- check Horizontal
        if chip_arr[x_idx][y_idx][0] == "H":
            wire = cord = chip_arr[x_idx][y_idx][1]
            for i in range(1, 5):
                if (y_idx+i) <= len(chip_arr[x_idx])-1:
                    if chip_arr[x_idx][y_idx][0] == chip_arr[x_idx][y_idx+i][0]:
                        add += 1

                if (y_idx-i) >= 0:
                    if chip_arr[x_idx][y_idx][0] == chip_arr[x_idx][y_idx-i][0]:
                        add += 1
    # -- check Vertical
        if chip_arr[x_idx][y_idx][0] == "V":
            wire = cord = chip_arr[x_idx][y_idx][1]
            for i in range(1, 5):
                if (x_idx+i) <= (len(chip_arr)-1):
                    if chip_arr[x_idx][y_idx][0] == chip_arr[x_idx+i][y_idx][0]:
                        add += 1

                if (x_idx-i) >= 0:
                    if chip_arr[x_idx][y_idx][0] == chip_arr[x_idx-i][y_idx][0]:
                        add += 1

        cap_out_q.put([wire, add])
        # cap_in_q.task_done()


if __name__ == '__main__':

    n_of_cpu = int(input("Enter the number of CPUs: "))
    DB_dir = "C:\OS_PROJECT\work_circuits"
    files = os.listdir(DB_dir)
    for file in files:
        p_list = list()
        in_q: Queue = Queue()
        out_q: Queue = Queue()

        # -------------- read file -------------------------------
        f = open(DB_dir + '\\' + file)
        l = f.readline().split()  # first line contains the chip's size
        # create 2D-array corresponding to the size of the chip
        chip_arr = [["-" for i in range(int(l[1])+1)]
                    for j in range(int(l[2])+1)]
        lines = f.readlines()
        nets: List[tuple[int, list[str]]] = [
            (0, []) for i in range(len(lines))]
        tot_resistance = [0 for i in range(len(lines))]
        tot_capacitance = [0 for i in range(len(lines))]
        idx = 0
        for line in lines:
            l = line.split()
            nets[idx] = (int((re.findall('(\d+)', l[0]))[0]),
                         re.findall('(\d+,\d+)+', l[1]))
            idx += 1
        f.close()
        nets.sort()

        # ---------------------------------------------------------
        print("finished read file")
        # --------- processes for resistance calculations----------
        for i in range(n_of_cpu):  # process initiation
            p = Process(target=calc_resistance, args=(in_q, out_q))
            p.start()
            p_list.append(p)

        # -- transfer a wire to a process
        for net in nets:
            wire = [net[1], net[0]]
            in_q.put(wire)  # wire[0] = cordinations of the wire
            # wire[1] = wire's index

        # -- get from a process the resistace of the wire
        for idx in range(len(nets)):
            data = out_q.get()
            # data[0] == wire's resistance value
            tot_resistance[data[1]] = data[0]
            # data[1] == wire index
        for p in p_list:
            p.terminate()

        # -------------------------------------------------------------
        print("finished calc res")
        # ---------------- chip array -------------------
        # c_p_list = list()
        c_in_q: Queue = Queue()
        c_out_q: Queue = Queue()
        n_nets = len(nets)
        p = Process(target=nets2chip, args=(chip_arr, c_in_q, c_out_q))
        p.start()

        for i in range(len(nets)):
            c_in_q.put(nets[i])
        c_in_q.put("END")
        chip_arr = c_out_q.get()
        p.terminate()
        # -------------------------------------------------------------
        print("finished chip arr")
        # --------- processes for capacitnace calculations----------
        cap_p_list = list()
        cap_in_q: JoinableQueue = JoinableQueue()
        cap_out_q: JoinableQueue = JoinableQueue()
        for _ in range(n_of_cpu):
            p = Process(target=calc_capacitance, args=(
                chip_arr, cap_in_q, cap_out_q))
            p.start()
            cap_p_list.append(p)
        for x_idx in range(len(chip_arr)):
            for y_idx in range(len(chip_arr[x_idx])):
                cord = [x_idx, y_idx]
                print(x_idx, y_idx)
                cap_in_q.put(cord)
                data = cap_out_q.get()
                tot_capacitance[data[0]] += data[1]
                # cap_in_q.join()

        for p in cap_p_list:
            p.terminate()
        # -------------------------------------------------------------
        print("finished calc cap")
        # -------------------- save to result file --------------------
        res_file = file.split('.')
        f = open(res_file[0]+'.res', 'a')
        for i in range(len(nets)):
            f.write("net{0:<20} {1:<8} {2:<8}\n".format(
                (i), tot_resistance[i], tot_capacitance[i]))
        f.close()
        print("finished file")
        break
