"""Classic Sod's shock-tube test.

Two regions of a quiescient gas are separated by an imaginary
diaphgram that is instantaneously ruptured at t = 0. The two states
(left,right) are defined by the properties:

     left                               right
  
     density = 1.0                      density = 0.125
     pressure = 1.0                     pressure = 0.1

The solution examined at the final time T = 0.15s

"""

# NumPy and standard library imports
import numpy

# PySPH base and carray imports
from pysph.base.nnps import DomainManager
from pysph.base.utils import get_particle_array_gasd as gpa
from pysph.base.kernels import CubicSpline, Gaussian

# PySPH solver and integrator
from pysph.solver.application import Application
from pysph.solver.solver import Solver
from pysph.sph.integrator import PECIntegrator
from pysph.sph.integrator_step import GasDFluidStep

# PySPH sph imports
from pysph.sph.equation import Group
from pysph.sph.gas_dynamics.basic import ScaleSmoothingLength, UpdateSmoothingLengthFromVolume,\
    SummationDensity, IdealGasEOS, MPMAccelerations

# PySPH tools
from pysph.tools import uniform_distribution as ud

# Numerical constants
dim = 1
gamma = 1.4
gamma1 = gamma - 1.0

# solution parameters
dt = 1e-4
tf = 0.15

# domain size and discretization parameters
xmin = 0; xmax = 1.0
nl = 320; nr = 40
dxl = 0.5/nl; dxr = 8*dxl

# scheme constants
alpha1 = 1.0
alpha2 = 0.1
beta = 2.0
kernel_factor = 1.2
h0 = kernel_factor*dxr

# The SPH kernel
kernel = Gaussian(dim=dim)

def create_particles(**kwargs):
    # particle positions
    x1 = numpy.arange( 0.5*dxl, 0.5, dxl )
    x2 = numpy.arange( 0.5 + 0.5*dxr, 1.0, dxr )
    x = numpy.concatenate( [x1, x2] )

    # indices on either side of the initial discontinuity
    right_indices = numpy.where( x > 0.5 )[0]

    # density
    rho = numpy.ones_like(x)
    rho[right_indices] = 0.125
    
    # pl = 1.0, pr = 0.1
    p = numpy.ones_like(x)
    p[right_indices] = 0.1
    
    # const h and mass
    h = numpy.ones_like(x) * h0
    m = numpy.ones_like(x) * dxl

    # thermal energy from the ideal gas EOS
    e = p/(gamma1*rho)

    fluid = gpa(name='fluid', x=x, rho=rho, p=p, e=e, h=h, m=m, h0=h.copy())

    print "2D Shocktube with %d particles"%(fluid.get_number_of_particles())

    return [fluid,]

# Create the application.
domain = DomainManager(
    xmin=xmin, xmax=xmax, periodic_in_x=True)

app = Application(domain=domain)

# Create the Integrator.
integrator = PECIntegrator(fluid=GasDFluidStep())

# Create the soliver
solver = Solver(kernel=kernel, dim=dim, integrator=integrator,
                dt=dt, tf=tf, adaptive_timestep=False, pfreq=50)

# Define the SPH equations
equations = [

    ################ BEGIN ADAPTIVE DENSITY-H ###################
    # For the Newton-Raphson, iterative solution for the
    # density-smoothing length relation, we use place the
    # SummationDensity Equation in a Group with the iterate argumet
    # set to True. After this Group, the density and the consitent
    # smoothing length is available for the particles.

    Group(
        equations=[
            SummationDensity(dest='fluid', sources=['fluid',], 
                             k=kernel_factor, density_iterations=True, dim=1, htol=1e-3),
            ], update_nnps=True, iterate=True, max_iterations=50,
        ),

    # # # For the GSPH density and smoothing length update algorithm, we
    # # # first scale the smoothing lengths to get the pilot density
    # # # estimate. Since the particle smoothing lengths are updated, we
    # # # need to re-compute the neighbors.
    
    # Group( equations=[
    #        ScaleSmoothingLength(dest='fluid', sources=None, factor=2.0), ],
    #       update_nnps=True ),

    # # # Given the new smoothing lengths and (possibly) new neighbors, we
    # # # compute the pilot density.

    # Group(
    #    equations=[
    #        SummationDensity(dest='fluid', sources=['fluid',]),
    #        ], update_nnps=False
    #    ),

    # # # Once the pilot density has been computed, we can update the
    # # # smoothing length from the new estimate of particle volume. Once
    # # # again, the NNPS must be updated to reflect the updated smoothing
    # # # lengths

    # Group(
    #     equations=[
    #         UpdateSmoothingLengthFromVolume(
    #             dest='fluid', sources=None, k=kernel_factor, dim=dim),
    #         ], update_nnps=True
    #     ),    

    # # # Now that we have the correct smoothing length, we need to
    # # # evaluate the density which will be used in the
    # # # accelerations.

    # Group(
    #    equations=[
    #        SummationDensity(dest='fluid', sources=['fluid',]),
    #        ], update_nnps=False
    #    ),

    ################ END ADAPTIVE DENSITY-H ###################

    # Now that we hav the updated density and smoothing lengths, we
    # can update the pressure and sound speed with the equation of
    # state.

    Group(
        equations=[
            IdealGasEOS(dest='fluid', sources=None, gamma=gamma),
            ], update_nnps=False
        ),

    # We're all set to compute the accelerations now
    Group(
        equations=[
            MPMAccelerations(dest='fluid', sources=['fluid',],
                              alpha1=alpha1, alpha2=alpha2, beta=beta)
            ], update_nnps=False
        ),
    ]

# Setup the application and solver.
app.setup(solver=solver, equations=equations,
          particle_factory=create_particles)

# run the solver
app.run()
