# http://docs.openstack.org/developer/python-novaclient/ref/v2/servers.html
import time, os, sys, random, re
import inspect
from os import environ as env
from pathlib import Path

# Add parent directory to sys.path to import constants
sys.path.insert(0, str(Path(__file__).parent.parent))

from  novaclient import client
import keystoneclient.v3.client as ksclient
from keystoneauth1 import loading
from keystoneauth1 import session
from constants import FLAVOR, PRIVATE_NET, IMAGE_NAME

flavor = FLAVOR
private_net = PRIVATE_NET
floating_ip_pool_name = None
floating_ip = None
image_name = IMAGE_NAME

identifier = random.randint(1000,9999)

loader = loading.get_plugin_loader('password')

auth = loader.load_from_options(auth_url=env['OS_AUTH_URL'],
                                username=env['OS_USERNAME'],
                                password=env['OS_PASSWORD'],
                                project_name=env['OS_PROJECT_NAME'],
                                project_domain_id=env['OS_PROJECT_DOMAIN_ID'],
                                #project_id=env['OS_PROJECT_ID'],
                                user_domain_name=env['OS_USER_DOMAIN_NAME'])

sess = session.Session(auth=auth)
nova = client.Client('2.1', session=sess)
print ("user authorization completed.")

image = nova.glance.find_image(image_name)

flavor = nova.flavors.find(name=flavor)

if private_net != None:
    net = nova.neutron.find_network(private_net)
    nics = [{'net-id': net.id}]
else:
    sys.exit("private-net not defined.")

#print("Path at terminal when executing this file")
#print(os.getcwd() + "\n")
cfg_file_path =  os.getcwd()+'/cloud-cfg.txt'
if os.path.isfile(cfg_file_path):
    with open(cfg_file_path) as f:
        userdata = f.read()
else:
    sys.exit("cloud-cfg.txt is not in current working directory")

secgroups = ['default']

print ("Creating instances ... ")
# instance = nova.servers.create(name="prod_server_without_docker_"+str(identifier), image=image, key_name='sztoor', flavor=flavor,userdata=userdata, nics=nics,security_groups=secgroups)


vm_names = ["arnab-a4-ray-head", "arnab-a4-ray-worker-1", "arnab-a4-ray-worker-2"]
instances = []

# craeting 3 instances with the same configuration but different names.
for vm_name in vm_names:
    instance = nova.servers.create(
        name=vm_name, 
        image=image, 
        flavor=flavor, 
        key_name='de1-course-snic-key',
        userdata=userdata, 
        nics=nics,
        security_groups=secgroups
    )
    instances.append(instance)
    print ("waiting for 10 seconds.. ")
    time.sleep(10)


for instance in instances:
    inst_status = instance.status
    print ("waiting for 10 seconds.. ")
    time.sleep(10)

    while inst_status == 'BUILD':
        print ("Instance: "+instance.name+" is in "+inst_status+" state, sleeping for 5 seconds more...")
        time.sleep(5)
        instance = nova.servers.get(instance.id)
        inst_status = instance.status

    ip_address = None
    for network in instance.networks[private_net]:
        if re.match('\d+\.\d+\.\d+\.\d+', network):
            ip_address = network
            break
    if ip_address is None:
        raise RuntimeError('No IP address assigned!')

    print ("Instance: "+ instance.name +" is in " + inst_status + " state" + " ip address: "+ ip_address)
