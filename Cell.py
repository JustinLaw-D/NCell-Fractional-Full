# contains class for a single atmospheric layer (Cell), satallites (functions more as a struct), and
# discrete events (Event)

import numpy as np
from BreakupModel import *
from ObjectsEvents import *
import os
import csv
G = 6.67430e-11 # gravitational constant (N*m^2/kg^2)
Me = 5.97219e24 # mass of Earth (kg)
Re = 6371 # radius of Earth (km)

class Cell:
    
    def __init__(self, S_i, S_di, D_i, R_i, N_i, logL_edges, chi_edges, event_list, alt, dh, tau_N, v, m_sat, sigma_sat,
                 del_t, fail_t, tau_do, target_alt, up_time, alpha_S, alpha_D, alpha_N, alpha_R, P, AM_sat, tau_sat, C_sat, 
                 expl_rate_L, expl_rate_D, m_rb, sigma_rb, lam_rb, AM_rb, tau_rb, C_rb, expl_rate_R):
        '''Constructor for Cell class
    
        Parameter(s):
        S_i : list of initial live satellite values for each satellite type
        S_di : list of initial de-orbiting satellite values for each satellite type
        D_i : list of initial derelict satellite values for each satellite type
        R_i : list of initial number of rocket bodies of each type
        N_i : initial array of number of debris by L and A/M
        logL_edges : bin edges in log10 of characteristic length (log10(m))
        chi_edges : bin edges in log10(A/M) (log10(m^2/kg))
        event_list : list of discrete events that occur in the cell
        alt : altitude of the shell centre (km)
        dh : width of the shell (km)
        tau_N : array of atmospheric drag lifetimes for debris (yr)
        v : relative collision speed (km/s)
        m_sat : mass of each satellite type (kg)
        sigma_sat : collision cross-section of each satellite type (m^2)
        del_t : mean satellite lifetime of each type (yr)
        fail_t : ascending satellite failure lifetime (yr)
        tau_do : mean time for satellites of each type to de-orbit from shell (yr)
        target_alt : target final altitude for each satellite type (km)
        up_time : amount of time it takes a satellite of each type to ascend through the band (yr)
        alpha_S : the fraction of collisions a live satellite of each type fails to avoid with a live satellite
        alpha_D : the fraction of collisions a live satellite of each type fails to avoid with a derelict satellite
        alpha_N : the fraction of collisions a live satellite of each type fails to avoid with trackable debris
        alpha_R : the fraction of collisions a live satellite of each type fails to avoid with a rocket
        P : post-mission disposal probability for satellites of each type
        AM_sat : area-to-mass ratio for satellites of each type (m^2/kg)
        tau_sat : atmospheric drag lifetime of each satellite type (yr)
        C_sat : fit constant for explosions for each satellite type
        expl_rate_L : number of explosions that occur in a 1yr period with a population 
                      of 100 live satellites, for each satellite type
        expl_rate_D : number of explosions that occur in a 1yr period with a population 
                      of 100 derelict satellites, for each satellite type
        m_rb : mass of each rocket body type (kg)
        sigma_rb : collision cross-section of each rocket body type (m^2)
        lam_rb : launch rate of each rocket body type into the shell (1/yr)
        AM_rb : area-to-mass ratio of each rocket body type (m^2/kg)
        tau_rb : atmospheric drag lifetime of each rocket body type (yr)
        C_rb : fit constant for explosions of each rocket body type
        expl_rate_R : number of explosions that occur in a 1yr period with a population 
                      of 100 rocket bodies, for each type

        Output(s):
        Cell instance
        '''

        # setup initial values for tracking satallites TODO
        self.num_sat_types = len(S_i)
        self.num_rb_types = len(R_i)
        self.S = [S_i]
        self.S_d = [S_di]
        self.D = [D_i]
        self.m_sat = m_sat
        self.sigma_sat = sigma_sat
        self.del_t = del_t
        self.fail_t = fail_t
        self.tau_do = tau_do
        self.target_alt = target_alt
        self.up_time = up_time
        self.alpha_S = alpha_S
        self.alpha_D = alpha_D
        self.alpha_R = alpha_R
        self.alpha_N = alpha_N
        self.P = P
        self.AM_sat = AM_sat
        self.tau_sat = tau_sat
        self.C_sat = C_sat
        self.expl_rate_L = expl_rate_L
        self.expl_rate_D = expl_rate_D

        # setup initial values for tracking rockets
        self.R = [R_i]
        self.m_rb = m_rb
        self.sigma_rb = sigma_rb
        self.lam_rb = lam_rb
        self.AM_rb = AM_rb
        self.tau_rb = tau_rb
        self.C_rb = C_rb
        self.expl_rate_R = expl_rate_R

        # setup initial debris values
        self.N_bins = [N_i]

        # setup other variables
        self.C_c = [0] # catastrophic collisions
        self.C_nc = [0] # non-catastrophic collisions
        self.event_list = event_list
        self.alt = alt
        self.dh = dh
        self.tau_N = tau_N
        self.v = v
        self.v_orbit = np.sqrt(G*Me/((Re + alt)*1000))/1000 # orbital velocity in km/s
        self.logL_edges = logL_edges
        self.num_L = len(logL_edges) - 1
        self.logL_ave = np.zeros(self.num_L) # average logL value in each bin
        for i in range(self.num_L):
            self.logL_ave[i] = (logL_edges[i]+logL_edges[i+1])/2
        self.L_ave = 10**self.logL_ave
        self.chi_edges = chi_edges
        self.num_chi = len(chi_edges) - 1
        self.chi_ave = np.zeros(self.num_chi) # average chi value in each bin
        for i in range(self.num_chi):
            self.chi_ave[i] = (chi_edges[i]+chi_edges[i+1])/2
        self.AM_ave = 10**self.chi_ave
        self.trackable = np.full(self.num_L, True) # which bins are trackable
        for i in range(self.num_L):
            ave_L = 10**((self.logL_edges[i] + self.logL_edges[i+1])/2) # average L value for these bins
            if ave_L < 1/10 : self.trackable[i] = False
        self.cat_sat_N = np.full((self.num_sat_types, self.num_L, self.num_chi), False) # tracks which collisions are catastrophic
        self.cat_rb_N = np.full((self.num_rb_types, self.num_L, self.num_chi), False)
        self.update_cat_N()
        self.ascending = np.full(self.num_sat_types, False) # list of which satellite types are ascending
        for i in range(self.num_sat_types):
            if self.target_alt[i] > self.alt + self.dh/2 : self.ascending[i] = True

    def save(self, filepath, filter, filter_len):
        ''' TODO
        saves the current Cell object to .csv and .npz files

        Input(s):
        filepath : explicit path to folder that the files will be saved in (string)
        filter : array of which data points to keep or skip (array of booleans)
        filter_len : number of Trues in the filter

        Output(s): None

        Note(s): event_list is lost, filter should be the same size as the t array from
                 NCell.
        '''

        # save parameters
        csv_file = open(filepath + 'params.csv', 'w', newline='')
        csv_writer = csv.writer(csv_file, dialect='unix')
        csv_writer.writerow([self.num_sat_types, self.num_rb_types, self.alt, self.dh, self.v, self.v_orbit, self.num_L,
                              self.num_chi])
        csv_file.close()

        # write easy arrays
        Cc_array, Cnc_array = np.array(self.C_c)[filter], np.array(self.C_nc)[filter]
        to_save = {'C_c' : Cc_array, 'C_nc' : Cnc_array, 'tau_N' : self.tau_N, 'trackable' : self.trackable,
                   'ascending' : self.ascending, 'logL' : self.logL_edges, 'chi' : self.chi_edges}
        np.savez_compressed(filepath + "data.npz", **to_save)

        # write N_bins values
        N_dict = dict()
        index = 0
        for i in range(len(self.N_bins)):
            if filter[i]:
                N_dict[str(index)] = self.N_bins[i]
                index += 1
        np.savez_compressed(filepath + "N_bins.npz", **N_dict)

        # write cat table values
        cat_dict = {'sat' : self.cat_sat_N, 'rb' : self.cat_rb_N}
        np.savez_compressed(filepath + "cat_tables.npz", **cat_dict)

        # write satellites and rockets
        for i in range(self.num_sat_types):
            sat_path = filepath + 'Satellite' + str(i) + '/'
            os.mkdir(sat_path)
            self.save_sat(sat_path, filter, filter_len, i)
        for i in range(self.num_rb_types):
            rb_path = filepath + 'RocketBody' + str(i) + '/'
            os.mkdir(rb_path)
            self.rockets[i].save(rb_path, filter)

    def save_sat(self, filepath, filter, filter_len, i):
        '''
        saves the current satellite information to .csv and .npz files

        Input(s):
        filepath : explicit path to folder that the files will be saved in (string)
        filter : array of which data points to keep or skip (array of booleans)
        filter_len : number of Trues in the filter
        i : satellite type number

        Output(s): None
        '''

        # save parameters
        csv_file = open(filepath + 'params.csv', 'w', newline='')
        csv_writer = csv.writer(csv_file, dialect='unix')
        csv_writer.writerow([self.m_sat[i], self.sigma_sat[i], self.del_t[i], self.fail_t[i], self.tau_do[i], 
                             self.target_alt[i], self.up_time[i], self.alphaS[i], self.alphaD[i], self.alphaN[i], 
                             self.alphaR[i], self.P[i], self.AM_sat[i], self.tau_sat[i], self.C_sat[i], 
                             self.expl_rate_L[i], self.expl_rate_D[i]])
        csv_file.close()

        # save data
        S_array = np.empty(filter_len, dtype=np.double)
        Sd_array = np.empty(filter_len, dtype=np.double)
        D_array = np.empty(filter_len, dtype=np.double)
        index = 0
        for j in range(len(self.S)):
            if filter[j]:
                S_array[index] = self.S[j][i]
                Sd_array[index] = self.S_d[j][i]
                D_array[index] = self.D[j][i]
                index += 1
        to_save = {'S' : S_array, 'S_d' : Sd_array, 'D' : D_array}
        np.savez_compressed(filepath + "data.npz", **to_save)
    
    def save_rb(self, filepath, filter, filter_len, i):
        '''
        saves the current rocket body information to .csv and .npz files

        Input(s):
        filepath : explicit path to folder that the files will be saved in (string)
        filter : array of which data points to keep or skip (array of booleans)
        filter_len : number of Trues in the filter
        i : rocket body type number

        Output(s): None
        '''

        # save parameters
        csv_file = open(filepath + 'params.csv', 'w', newline='')
        csv_writer = csv.writer(csv_file, dialect='unix')
        csv_writer.writerow([self.m_rb[i], self.sigma_rb[i], self.lam_rb[i], self.AM_rb[i], self.tau_rb[i],
                             self.C_rb[i], self.expl_rate_R[i]])
        csv_file.close()

        # save data
        R_array = np.empty(filter_len, dtype=np.double)
        index = 0
        for j in range(len(self.R)):
            if filter[j]:
                R_array[index] = self.R[j][i]
                index += 1
        to_save = {'R' : R_array}
        np.savez_compressed(filepath + "data.npz", **to_save)

    def load(filepath):
        ''' TODO
        builds a Cell object from saved data

        Input(s):
        filepath : explicit path to folder that the files are saved in (string)

        Keyword Input(s): None

        Output(s):
        cell : Cell object build from loaded data

        Note(s): cell will not have events
        '''

        cell = Cell.__new__(Cell) # create blank Cell

        # load parameters
        csv_file = open(filepath + 'params.csv', 'r', newline='')
        csv_reader = csv.reader(csv_file, dialect='unix')
        for row in csv_reader: # there's only one row, this extracts it
            cell.num_sat_types = int(row[0])
            cell.num_rb_types = int(row[1])
            cell.alt = float(row[2])
            cell.dh = float(row[3])
            cell.v = float(row[4])
            cell.v_orbit = float(row[5])
            cell.num_L = int(row[6])
            cell.num_chi = int(row[7])
        csv_file.close()

        # load basic arrays
        array_dict = np.load(filepath + "data.npz")
        cell.C_c = array_dict['C_c'].tolist()
        cell.C_nc = array_dict['C_nc'].tolist()
        cell.tau_N = array_dict['tau_N']
        cell.trackable = array_dict['trackable']
        cell.ascending = array_dict['ascending']
        cell.logL_edges = array_dict['logL']
        cell.chi_edges = array_dict['chi']

        # load N_bins values
        cell.N_bins = []
        bins_dict = np.load(filepath + "N_bins.npz")
        i = 0
        while True:
            try:
                N_bins = bins_dict[str(i)]
                cell.N_bins.append(N_bins)
            except KeyError:
                break
            i += 1
        
        # load lethal table values
        cat_dict = np.load(filepath + "cat_tables.npz")
        cell.cat_sat_N = cat_dict['sat']
        cell.cat_rb_N = cat_dict['rb']

        # setup variables for satellites TODO

        for i in range(cell.num_sat_types):
            sat_path = filepath + 'Satellite' + str(i) + '/'
            cell.satellites.append(Satellite.load(sat_path))
        for i in range(cell.num_rb_types):
            rb_path = filepath + 'RocketBody' + str(i) + '/'
            cell.rockets.append(RocketBody.load(rb_path))

        cell.event_list = []
        return cell

    def dxdt_cell(self, time):
        ''' TODO
        calculates the rate of collisions and decays from each debris bin, the rate
        of decaying/de-orbiting satellites, the rate of launches/deorbit starts of satallites, 
        and the rate of creation of derelicts at the given time, due only to events in the cell

        Parameter(s):
        time : index of the values to use

        Keyword Parameter(s): None

        Output(s):
        dSdt : array of rate of change of the number of live satellites in the cell of each type due to only processes
               withing the cell (excluding satellites ascending) (yr^(-1))
        dS_ddt : array of rate of change of the number of de-orbiting satellites in the cell of each type
                 (excluding satellites de-orbiting) (yr^(-1))
        dDdt : array of rate of change of the number of derelict satellites in the cell of each type
               (excluding derelicts decaying) (yr^(-1))
        dRdt : array of rate of change of number of rocket bodies in the cell of each type (excluding rockets decaying) (yr^(-1))
        S_out : array of rate of satellites ascending from the cell of each type (yr^(-1))
        S_dout : array of rate of satellites de-orbiting from the cell of each type (yr^(-1))
        D_out : array of rate of satellites decaying from the cell of each type (yr^(-1))
        R_out : array of rate of rocket bodies decaying from the cell of each type (yr^(-1))
        N_out : matrix with the rate of exiting debris from each bin (yr^(-1))
        D_dt : matrix with total rate of collisions between satellites (yr^(-1))
        RD_dt : matrix with total rate of collisions between satellites and rocket bodies (yr^(-1))
        R_dt : matrix with total rate of collisions between rocket bodies (yr^(-1))
        CS_dt : array of matrices with the rate of collisions from each bin with each satellite type (yr^(-1))
        CR_dt : array of matrices with the rate of collisions from each bin with each rocket body type (yr^(-1))
        expl_S : array of rate of explosions for satellites of each type (yr^(-1))
        expl_R : array of rate of explosions for rocket bodies of each type (yr^(-1))

        Note: Assumes that collisions with debris of L_cm < 10cm cannot be avoided, and
        that the given time input is valid
        '''
        
        N = self.N_bins[time]

        # compute the rate of collisions from each debris type
        dSdt = np.zeros((self.num_sat_types, self.num_L, self.num_chi)) # collisions with live satallites
        dSSdt = np.zeros((self.num_sat_types, self.num_sat_types)) # collisions between live satellites
        dSS_ddt = np.zeros((self.num_sat_types, self.num_sat_types)) # collisions between live and de-orbiting satellites
        dSDdt = np.zeros((self.num_sat_types, self.num_sat_types)) # collisions between live and derelict satellites
        dSRdt = np.zeros((self.num_sat_types, self.num_rb_types)) # collisions between live satellites and rocket bodies
        # first index is live satellite type, second is derelict/rocket type
        dS_ddt = np.zeros((self.num_sat_types, self.num_L, self.num_chi)) # collisions with de-orbiting satallites
        dS_ddS_ddt = np.zeros((self.num_sat_types, self.num_sat_types)) # collisions between de-orbiting satellites
        dS_dDdt = np.zeros((self.num_sat_types, self.num_sat_types)) # collisions between de-orbiting and derelict satallites
        dS_dRdt = np.zeros((self.num_sat_types, self.num_rb_types)) # collisions between de-orbiting satellites and rocket bodies
        dDdt = np.zeros((self.num_sat_types, self.num_L, self.num_chi)) # collisions with derelict satallites
        dDDdt = np.zeros((self.num_sat_types, self.num_sat_types)) # number of collisions between derelict satallites
        dDRdt = np.zeros((self.num_sat_types, self.num_rb_types)) # collisions between derelict satellites and rocket bodies
        dRdt = np.zeros((self.num_rb_types, self.num_L, self.num_chi)) # collisions with rocket bodies
        dRRdt = np.zeros((self.num_rb_types, self.num_rb_types)) # collisions between rocket bodies
        decay_N = np.zeros(N.shape) # rate of debris that decay
        ascend_S = np.zeros(self.num_sat_types) # rate of satellites ascending into a higher orbit
        kill_S = np.zeros(self.num_sat_types) # rate of satellites being put into de-orbit
        deorbit_S = np.zeros(self.num_sat_types) # rate of satellites de-orbiting out of the band
        decay_D = np.zeros(self.num_sat_types) # rate of derelicts that decay
        decay_R = np.zeros(self.num_rb_types) # rate of rocket bodies that decay
        dSdt_tot = np.zeros(self.num_sat_types) # total rate of change for live satellites
        dS_ddt_tot = np.zeros(self.num_sat_types) # total rate of change for de-orbiting satellites
        dDdt_tot = np.zeros(self.num_sat_types) # total rate of change of derelict satellites
        dRdt_tot = np.zeros(self.num_rb_types) # total rate of change for rocket bodies
        CS_dt = np.zeros((self.num_sat_types, self.num_L, self.num_chi))
        CR_dt = np.zeros((self.num_rb_types, self.num_L, self.num_chi))
        expl_S = np.zeros(self.num_sat_types)
        expl_Sd = np.zeros(self.num_sat_types)
        expl_D = np.zeros(self.num_sat_types)
        expl_R = np.zeros(self.num_rb_types)

        for i in range(self.num_sat_types):

            # get current satellite type values
            S = self.satellites[i].S[time]
            S_d = self.satellites[i].S_d[time]
            D = self.satellites[i].D[time]
            sigma = self.satellites[i].sigma
            alphaS = self.satellites[i].alphaS
            alphaD = self.satellites[i].alphaD
            alphaN = self.satellites[i].alphaN
            alphaR = self.satellites[i].alphaR
            expl_rate_L = self.satellites[i].expl_rate_L
            expl_rate_D = self.satellites[i].expl_rate_D

            # handle debris events with satellites
            dSdt[i,:,:], dS_ddt[i,:,:], dDdt[i,:,:] = self.N_sat_events(S, S_d, D, N, sigma, alphaN)
        
            # compute collisions involving only satellities
            tot_S_sat_coll = 0 # total collisions destroying live satellites of this type
            tot_Sd_sat_coll = 0 # total collisions destroying de-orbiting satellites of this type
            tot_D_sat_coll = 0 # total collisions destroying derelicts of this type
            for j in range(self.num_sat_types):
                S2 = self.satellites[j].S[time]
                S_d2 = self.satellites[j].S_d[time]
                D2 = self.satellites[j].D[time]
                sigma2 = self.satellites[j].sigma
                alphaS2 = self.satellites[j].alphaS
                dSSdt[i,j], dSS_ddt[i,j], dSDdt[i,j], dS_ddS_ddt[i,j], dS_dDdt[i,j], dDDdt[i,j] = self.SColl_events(S, S_d, D, sigma, alphaS, alphaD, S2, S_d2, D2, sigma2, alphaS2)
                if i == j :
                    tot_S_sat_coll += 2*dSSdt[i,j] + dSS_ddt[i,j] + dSDdt[i,j]
                    tot_Sd_sat_coll += dSS_ddt[j,i] + 2*dS_ddS_ddt[i,j] + dS_dDdt[i,j]
                    tot_D_sat_coll += dSDdt[j,i] + dS_dDdt[j,i] + 2*dDDdt[i,j]
                else : 
                    tot_S_sat_coll += dSSdt[i,j] + dSS_ddt[i,j] + dSDdt[i,j]
                    tot_Sd_sat_coll += dSS_ddt[j,i] + dS_ddS_ddt[i,j] + dS_dDdt[i,j]
                    tot_D_sat_coll += dSDdt[j,i] + dS_dDdt[j,i] + dDDdt[i,j]
                if i > j: # avoid double counting later on
                    dSSdt[i,j] = 0
                    dS_ddS_ddt[i,j] = 0
                    dDDdt[i,j] = 0

            # compute collisions between satellites and rocket bodies
            for j in range(self.num_rb_types):
                R = self.rockets[j].num[time]
                sigma2 = self.rockets[j].sigma
                dSRdt[i,j], dS_dRdt[i,j], dDRdt[i,j] = self.SRColl_events(S, S_d, D, sigma, alphaR, R, sigma2)
                tot_S_sat_coll += dSRdt[i,j]
                tot_Sd_sat_coll += dS_dRdt[i,j]
                tot_D_sat_coll += dDRdt[i,j]

            # compute explosions for satellites
            expl_S[i] = expl_rate_L*S/100
            expl_Sd[i] = expl_rate_L*S_d/100
            expl_D[i] = expl_rate_D*D/100

            # compute decay/ascend events for satellites
            up_time = self.satellites[i].up_time
            del_t = self.satellites[i].del_t
            tau_do = self.satellites[i].tau_do
            tau = self.satellites[i].tau
            kill_S[i], deorbit_S[i], decay_D[i] = S/del_t, S_d/tau_do, D/tau
            if self.ascending[i] : ascend_S[i] = S/up_time

            # sum everything up
            P = self.satellites[i].P
            dSdt_tot[i] = 0 - kill_S[i] - np.sum(dSdt[i,:,:]) - tot_S_sat_coll - expl_S[i]
            dS_ddt_tot[i] = P*kill_S[i] - np.sum(dS_ddt[i,:,:]) - tot_Sd_sat_coll - expl_Sd[i]
            dDdt_tot[i] = (1-P)*kill_S[i] - np.sum(dDdt[i,:,:][self.lethal_sat_N[i] == True])  - tot_D_sat_coll + np.sum(dSdt[i,:,:][self.lethal_sat_N[i] == False]) + np.sum(dS_ddt[i,:,:][self.lethal_sat_N[i] == False]) - expl_D[i]
            CS_dt[i,:,:] = dSdt[i,:,:] + dS_ddt[i,:,:] + dDdt[i,:,:]

        for i in range(self.num_rb_types): # handle rocket body only events

            # get current rocket body values
            R = self.rockets[i].num[time]
            sigma = self.rockets[i].sigma
            lam = self.rockets[i].lam
            tau = self.rockets[i].tau
            expl_rate = self.rockets[i].expl_rate

            # handle rocket-debris collisions
            dRdt[i,:,:] = self.N_rb_events(R, N, sigma)

            # handle rocket-rocket collisions
            tot_R_coll = 0 # total collisions destroying rocket bodies of this type
            for j in range(self.num_rb_types):
                R2 = self.rockets[j].num[time]
                sigma2 = self.rockets[j].sigma
                dRRdt[i,j] = self.RColl_events(R, sigma, R2, sigma2)
                if i != j : tot_R_coll += dRRdt[i,j]
                else : tot_R_coll += 2*dRRdt[i,j]
                if i > j : dRRdt[i,j] = 0 # avoid double counting later on

            # add on satellite-rocket collisions
            tot_R_coll += np.sum(dSRdt[:,i]) + np.sum(dS_dRdt[:,i]) + np.sum(dDRdt[:,i])

            # handle rocket explosions
            expl_R[i] = expl_rate*R/100

            # handle rocket decays
            decay_R[i] = R/tau

            # sum everything up
            dRdt_tot[i] = lam - np.sum(dRdt[i,:,:][self.lethal_rb_N[i] == True]) - tot_R_coll - expl_R[i]
            CR_dt[i,:,:] = dRdt[i,:,:]

        # calculate rates of decay for debris
        decay_N = N/self.tau_N

        D_dt = dSSdt + dSS_ddt + dSDdt + dS_ddS_ddt + dS_dDdt + dDDdt
        RD_dt = dSRdt + dS_dRdt + dDRdt
        R_dt = dRRdt
        expl_S_tot = expl_S + expl_Sd + expl_D

        return dSdt_tot, dS_ddt_tot, dDdt_tot, dRdt_tot, ascend_S, deorbit_S, decay_D, decay_R, decay_N, D_dt, RD_dt, R_dt, CS_dt, CR_dt, expl_S_tot, expl_R

    def N_sat_events(self, S, S_d, D, N, sigma, alpha):
        ''' TODO
        calculates the rate of collisions between debris and stallites of a particular type in a band

        Parameter(s):
        S : number of live satellites in the band of this type
        S_d : number of de-orbiting satellites in the band of this type
        D : number of derelict satellites in the band of this type
        N : binned matrix of number of pieces of debris in the band
        sigma : cross section of the satellites (m^2)
        alpha : fraction of collisions a live satellites fails to avoid

        Keyword Parameter(s): None
        
        Output(s):
        dSdt : rates of collisions between debris and live satellites (1/yr)
        dS_ddt : rates of collisions between debris and de-orbiting satellites (1/yr)
        dDdt : rates of collisions between debris and derelict satellites (1/yr)
        '''
        sigma /= 1e6 # convert to km^2
        v = self.v*365.25*24*60*60 # convert to km/yr
        V = 4*np.pi*(6371 + self.alt)**2*self.dh # volume of the shell
        n = N/V # number density of the debris
        dSdt = n*sigma*v*S # compute rates of collision
        dS_ddt = n*sigma*v*S_d
        dDdt = n*sigma*v*D
        dSdt[self.trackable] *= alpha # account for collision avoidance
        dS_ddt[self.trackable] *= alpha
        return dSdt, dS_ddt, dDdt

    def N_rb_events(self, R, N, sigma):
        ''' TODO
        calculates the rate of collisions between debris and rocket bodies of a particular type in a band

        Parameter(s):
        R : number of rocket bodies in the band of this type
        N : binned matrix of number of pieces of debris in the band
        sigma : cross section of the rocket bodies (m^2)

        Keyword Parameter(s): None
        
        Output(s):
        dRdt : rate of collisions between debris and rocket bodies (1/yr)
        '''
        sigma /= 1e6 # convert to km^2
        v = self.v*365.25*24*60*60 # convert to km/yr
        V = 4*np.pi*(6371 + self.alt)**2*self.dh # volume of the shell
        n = N/V # number density of the debris

        return n*sigma*v*R

    def SColl_events(self, S1, S_d1, D1, sigma1, alphaS1, alphaD1, S2, S_d2, D2, sigma2, alphaS2):
        ''' TODO
        calculates the rate of collisions between satellites of two particular types
        in a band

        Parameter(s):
        S1 : number of live satellites of type 1
        S_d1 : number of de-orbiting satellites of type 1
        D1 : number of derelict satellites of type 1
        sigma1 : cross-section of satellites of type 1 (m^2)
        alphaS1 : fraction of collisions with a live satellite that a live satellites of type 1 fails to avoid
        alphaD1 : fraction of collisions with a derelict that a live satellites of type 1 fails to avoid
        S2 : number of live satellites of type 2
        S_d2 : number of de-orbiting satellites of type 2
        D2 : number of derelict satellites of type 2
        sigma2 : cross-section of satellites of type 2 (m^2)
        alphaS2 : fraction of collisions with a live satellite that a live satellites of type 2 fails to avoid

        Keyword Parameter(s): None

        Output(s):
        dSSdt : rate of collision between live satellites of type 1 and live satellites of type 2 (1/yr)
        dSS_ddt : rate of collision between live satellites of type 1 and de-orbiting satellites of type 2 (1/yr)
        dSDdt : rate of collision between live satellites of type 1 and derelicts of type 2 (1/yr)
        dS_dS_ddt : rate of collision between de-orbiting satellites of type 1 and de-orbiting satellites of type 2 (1/yr)
        dS_dDdt : rate of collision between de-orbiting satellites of type 1 and derelicts of type 2 (1/yr)
        dDDdt : rate of collision between derelict satellites of type 1 and derelicts of type 2 (1/yr)
        '''

        sigma1 /= 1e6 # convert to km^2
        sigma2 /= 1e6
        sigma = sigma1 + sigma2 + 2*np.sqrt(sigma1*sigma2) # account for increased cross-section
        v = self.v*365.25*24*60*60 # convert to km/yr
        V = 4*np.pi*(6371 + self.alt)**2*self.dh # volume of the shell

        # rate of collisions between derelicts and satallites (live/derelict)
        dSSdt = alphaS1*alphaS2*sigma*v*S1*S2/V
        dSS_ddt = alphaS1*alphaS2*sigma*v*S1*S_d2/V
        dSDdt = alphaD1*sigma*v*S1*D2/V
        dS_dS_ddt = alphaS1*alphaS2*sigma*v*S_d1*S_d2/V
        dS_dDdt = alphaD1*sigma*v*S_d1*D2/V
        dDDdt = sigma*v*D1*D2/V  # collisions cannot be avoided
        return dSSdt, dSS_ddt, dSDdt, dS_dS_ddt, dS_dDdt, dDDdt

    def SRColl_events(self, S1, S_d1, D1, sigma1, alpha1, R, sigma2):
        ''' TODO
        calculates the rate of collisions between satellites and rocket bodies of two particular types
        in a band

        Parameter(s):
        S1 : number of live satellites of a particular type
        S_d1 : number of de-orbiting satellites of a particular type
        D1 : number of derelict satellites of a particular type
        sigma1 : cross-section of satellites (m^2)
        alpha1 : fraction of collisions a live satellites fails to avoid
        R : number of rocket bodies of the particular type
        sigma2 : cross-section of rocket bodies (m^2)

        Keyword Parameter(s): None

        Output(s):
        dSRdt : rate of collision between live satellites of type 1 and rocket bodies (1/yr)
        dS_dRdt : rate of collision between de-orbiting satellites of type 1 and rocket bodies (1/yr)
        dDDdt : rate of collision between derelict satellites of type 1 and rocket bodies (1/yr)
        '''

        sigma1 /= 1e6 # convert to km^2
        sigma2 /= 1e6
        sigma = sigma1 + sigma2 + 2*np.sqrt(sigma1*sigma2) # account for increased cross-section
        v = self.v*365.25*24*60*60 # convert to km/yr
        V = 4*np.pi*(6371 + self.alt)**2*self.dh # volume of the shell
        n = R/V # number density of the rockets

        # rate of collisions between satellites and rockets
        dSRdt = alpha1*n*sigma*v*S1
        dS_dRdt = alpha1*n*sigma*v*S_d1
        dDRdt = n*sigma*v*D1  # collisions cannot be avoided
        return dSRdt, dS_dRdt, dDRdt

    def RColl_events(self, R1, sigma1, R2, sigma2):
        ''' TODO
        calculates the rate of collisions between rocket bodies of two types in a band

        Parameter(s):
        R1 : number of rocket bodies of a type 1 in the band
        sigma1 : cross-section of rocket bodies of type 1 (m^2)
        R2 : number of rocket bodies of a type 2 in the band
        sigma2 : cross-section of rocket bodies of type 2 (m^2)

        Keyword Parameter(s): None

        Output(s):
        dRRdt : rate of collision between the two types of rocket bodies (1/yr)
        '''

        sigma1 /= 1e6 # convert to km^2
        sigma2 /= 1e6
        sigma = sigma1 + sigma2 + 2*np.sqrt(sigma1*sigma2) # account for increased cross-section
        v = self.v*365.25*24*60*60 # convert to km/yr
        V = 4*np.pi*(6371 + self.alt)**2*self.dh # volume of the shell
        n = R2/V # number density of the rockets of the second type
        return n*sigma*v*R1

    def update_cat_N(self):
        '''
        updates values in cat_N based on current mass, v, and bins

        Parameter(s): None

        Keyword Parameter(s): None

        Ouput(s): None
        '''

        for i in range(self.num_sat_types):
            for j in range(self.num_L):
                for k in range(self.num_chi):
                    self.cat_sat_N[i,j,k] = is_catastrophic(self.m_sat[i], self.L_ave[j], self.AM_ave[k], self.v)
        for i in range(self.num_rb_types):
            for j in range(self.num_L):
                for k in range(self.num_chi):
                    self.cat_rb_N[i,j,k] = is_catastrophic(self.m_rb[i], self.L_ave[j], self.AM_ave[k], self.v)
