from flask import Blueprint, render_template, session, redirect, request, jsonify
from flask_login import login_required, current_user
from . import *
import random
import string
import subprocess
import docker
from docker import *

main = Blueprint('main', __name__)

networkCount = 0
docker_limit = 100
portlist = []
namelist = []
nameurl = {}
dockerlist = {}
client = docker.from_env()
number_of_subnets = 0


@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)


# Using this to generate the names/passwords for the docer containers
def randomStringDigits(stringLength=10):
    """Generate a random string of letters and digits """
    lettersAndDigits = string.ascii_letters + string.digits
    return ''.join(random.choice(lettersAndDigits) for i in range(stringLength))


def spaceForDocker(count):
    return bool(int(subprocess.check_output("docker container ls --all | wc -l", shell=True).decode("utf-8")) > count)


def generatePort():
    global portlist
    port = random.randint(30000, 50000)
    while port in portlist:
        port = random.randint(30000, 50000)
    portlist.append(port)
    return port


def generateName():
    global namelist
    container = randomStringDigits(10)
    while container in namelist:
        container = randomStringDigits(10)
    namelist.append(container)
    return container


# This function creates a new docker network with a unique subnet
def newNetwork(subnet):
    global client
    # class IPAMPool(subnet=None, iprange=None, gateway=None, aux_addresses=None)
    #       Create an IPAM pool config dictionary to be added to the pool_configs parameter of IPAMConfig.
    ipam_pool = docker.types.IPAMPool(
        subnet=subnet
    )

    # class IPAMConfig(driver='default', pool_configs=None, options=None)
    #       Create an IPAM (IP Address Management) config dictionary to be used with create_network().
    ipam_config = docker.types.IPAMConfig(
        pool_configs=[ipam_pool]
    )

    #  create(name, *args, **kwargs)
    #       Create a network. Similar to the docker network create.
    try:
        client.networks.create(
            str(session['container']),
            ipam=ipam_config
        )
    except RuntimeError as e:
        print("WARNING!!! Network already exists.")
        print(e)


def newContainer(imageName):
    global networkCount
    global dockerlist
    global client
    session['port'] = generatePort()
    session['container'] = generateName()
    session['password'] = randomStringDigits(20)
    # Adding this to the master list
    dockerlist[session['container']] = session['port']
    newNetwork(('172.11.' + str(networkCount % 256) + '.0/24'))
    client.containers.run(imageName,
                          tty=True,
                          detach=True,
                          network=str(session['container']),
                          name=str(session['container']),
                          user='0',
                          ports={'6901/tcp': str(session['port'])},
                          environment=["VNC_PW=" + str(session['password']),
                                       "VNC_RESOLUTION=800x600"])
    networkCount += 1

def check():
    email = current_user.email
    if email in namelist:
        return True
    else:
        return False


def getDocker(imageName):

    global namelist
    global nameurl
    print(nameurl)
    if nameurl.get(str(current_user.email))is not None:
        return nameurl[str(current_user.email)]
    else:
        newContainer(imageName)
        url = ('http://' + str(host) + ':' + str(session['port']) + '/?password=' + str(session['password']))
        print(url)
        nameurl[str(current_user.email)] = url
        return nameurl[str(current_user.email)]


@main.route('/router')
def router():
    global portlist
    global namelist
    global dockerlist
    global docker_limit
    print(dockerlist)
    # Sorry all out of containers html page... Create one!!
    if spaceForDocker(docker_limit):
        return render_template('error.html')
    url = getDocker('atr2600/zenmap-vnc-ubuntu')
    return redirect(url)


@main.route('/')
@login_required
def index():
    global portlist
    global namelist
    global dockerlist
    global docker_limit
    print(dockerlist)
    # Sorry all out of containers html page... Create one!!
    if spaceForDocker(docker_limit):
        return render_template('error.html')
    url = getDocker('atr2600/zenmap-vnc-ubuntu')
    return redirect(url)


# Yes this should be limited to only the admin role..
# I do not have enough time to implement this right now.
@main.route('/admin', methods=['GET', 'POST'])
def admin():
    global number_of_subnets

    # Here we are going to get some settings from the admin.

    if request.method == 'POST':
        number_of_subnets = request.form.get('number_of_subnets')
        return redirect('/admin')


    if request.method == 'GET':
        return render_template("admin.html")



####
## This function does:
## 1. Removes the port and name from the portlist and namelist
## 2. Removes the container from the master list.
## 3. Clears the session
## 4. Sends kill docker command to the system.
####
def destroy():
    global portlist
    global namelist
    global dockerlist
    global client
    # killing docker container
    client.containers.get(session['container']).remove(force=True)
    client.networks.prune(filters=None)
    # Cleaning up the port numbers and container name
    portlist.remove(dockerlist[session['container']])
    namelist.remove(session['container'])
    del dockerlist[session['container']]
    print('Killed container: ' + session['container'])
    session.clear()
