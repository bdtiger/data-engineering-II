import syft as sy

# Replace with your actual Worker VM IPs
ds_client_a = sy.login(
    url="http://192.168.2.197:8080",
    email="info@openmined.org",
    password="changethis"
)

ds_client_b = sy.login(
    url="http://192.168.2.254:8080",
    email="info@openmined.org",
    password="changethis"
)

print(ds_client_a)   # Should show "ClientA" node info
print(ds_client_b)   # Should show "ClientB" node info