# contains models for atmospheric density, drag lifetime

import os
import numpy as np

G = 6.67430e-11 # gravitational constant (N*m^2/kg^2)
Me = 5.97219e24 # mass of Earth (kg)
Re = 6371 # radius of Earth (km)

filepath, _ = os.path.split(__file__) # path to current folder
filepath += '/'

# read density model
atmfile=open(filepath + "atmosphere_data/cira-2012.dat","r")
header=atmfile.readline()
zmodel=[]
denmodelL=[]
denmodelM=[]
denmodelHL=[]
for line in atmfile:
  alt,low,med,highL,_=line.split()
  zmodel.append(float(alt))
  denmodelL.append(float(low))
  denmodelM.append(float(med))
  denmodelHL.append(float(highL))

atmfile.close()

zmodel=np.array(zmodel)*1000 # convert to m
denmodelL=np.array(denmodelL)
denmodelM=np.array(denmodelM)
denmodelHL=np.array(denmodelHL)

logdenL = np.log10(denmodelL)
logdenM = np.log10(denmodelM)
logdenHL = np.log10(denmodelHL)
logz = np.log10(zmodel)

# read solar cycle template (using F10.7 as the solar activity index)
f107file = open(filepath + "atmosphere_data/solar_cycle_table36_cira2012.dat","r")
header=f107file.readline()
f107_mo=[]
for line in f107file:
   mo,_,f107,_,_,_,_,_,_,_,_,_,_=line.split()
   f107_mo.append(float(f107))
f107file.close()
f107_mo=np.array(f107_mo) 

def density(alt,t,mo0,setF107):
    '''
    Calculates the atmospheric density at a given altitude via interpolation

    Parameter(s):
    alt : altitude (km)
    t : time since arbitrary start point (yr)
    m0 : starting month in the solar cycle (int)
    setF107 : if not None, value taken for solar flux regardless of current time (None or 10^(-22)W/m^2)

    Output(s):
    rho : atmospheric density at the given altitude and time (kg/m^3)
    '''

    i=int((alt-100)/20) # calculate index for altitude
    if i > len(zmodel)-2: i=len(zmodel)-2
    if i < 0: i=0

    try:
       logalt = np.log10(alt) + 3 # convert to m
    except:
       logalt = 0.
 
    mo_frac = t*12 + mo0

    mo = mo_frac % 144

    moID = int(mo)

    if setF107==None: # get flux value
       moID1 = moID+1
       if moID1>143:moID1=0
       F107 = f107_mo[moID] + (f107_mo[moID1]-f107_mo[moID])*(mo-moID)
    else: F107 = setF107

    if F107 <= 65: # interpolate to get density value
       rho = 10.**(  logdenL[i]+(logdenL[i+1]-logdenL[i])/(logz[i+1]-logz[i])*(logalt-logz[i]) )

    elif F107 <= 140:
      d0 = 10.**(  logdenL[i]+(logdenL[i+1]-logdenL[i])/(logz[i+1]-logz[i])*(logalt-logz[i]) )
      d1 = 10.**(  logdenM[i]+(logdenM[i+1]-logdenM[i])/(logz[i+1]-logz[i])*(logalt-logz[i]) )
      rho = d0 + (d1-d0)*(F107-65.)/75.

    elif F107 <= 250:
      d0 = 10.**(  logdenM[i]+(logdenM[i+1]-logdenM[i])/(logz[i+1]-logz[i])*(logalt-logz[i]) )
      d1 = 10.**(  logdenHL[i]+(logdenHL[i+1]-logdenHL[i])/(logz[i+1]-logz[i])*(logalt-logz[i]) )
      rho = d0 + (d1-d0)*(F107-140.)/110.

    else:
      rho = 10.**(  logdenHL[i]+(logdenHL[i+1]-logdenHL[i])/(logz[i+1]-logz[i])*(logalt-logz[i]) )

    return rho

def dadt(alt, t, m0, a_over_m, CD, setF107):
    '''
    Calculates the rate of change in the altitude of a circular orbit

    Parameter(s):
    alt : altitude of the orbit (km)
    t : time passed since the start of the solar cycle (yr)
    m0 : starting month in the solar cycle
    a_over_m : area-to-mass ratio of the object (m^2/kg)
    CD : drag coefficient of the object
    setF107 : if not None, value taken for solar flux regardless of current time (None or 10^(-22)W/m^2)

    Outputs:
    dadt value (km/yr)
    '''
    return -(CD*density(alt, t, m0, setF107)*a_over_m*np.sqrt(G*Me*(alt + Re)*1e3))*60*60*24*365.25*1e-3

def drag_lifetime(alt_i, alt_f, a_over_m, CD, dt, m0, mindt, maxdt, dtfactor, tmax, setF107):
    '''
    Estimates the drag lifetime of an object at altitude alt_i to degrade to altitude alt_f

    Parameter(s):
    alt_i : initial altitude of the object (km)
    alt_f : desired final altitude of the object (km)
    a_over_m : area-to-mass ratio of the object (m^2/kg)
    CD : drag coefficient of the object
    dt : initial time step of the integration (yr)
    m0 : starting month in the solar cycle
    mindt : minimum time step for integration (yr)
    maxdt : maximum time step of the integration (yr or None)
    dtfactor : fraction of altitude/rate of change to take as dt
    tmax : maximum time to search to (yr)
    setF107 : if not None, value taken for solar flux regardless of current time (None or 10^(-22)W/m^2)

    Output(s):
    tau : drag lifetime, possibly infinite (yr)
    '''

    # initialize variables
    time = 0
    alt = alt_i

    # integrate using predictor-corrector method
    while alt > alt_f:
        dadt0 = dadt(alt, time, m0, a_over_m, CD, setF107)
        alt1 = alt + dadt0*dt
        dadt1 = dadt(alt1, time + dt, m0, a_over_m, CD, setF107)
        ave_dadt = (dadt0 + dadt1)/2
        alt += ave_dadt*dt
        time += dt
        dt = np.amin(-(alt/ave_dadt)*dtfactor)
        if dt < mindt:
            print('WARNING: Problem is possibly too stiff for integrator.')
            dt = mindt
        elif maxdt != None:
            dt = min(dt, maxdt)
        if tmax is not None: # give up?
            if time > tmax : return np.full(a_over_m.shape, np.inf)

    return time
