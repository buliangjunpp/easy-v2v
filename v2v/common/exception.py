class vSpherePropertyNotExist(Exception):
    def __init__(self, object_type):
        self.message = ("Referenced type %s in property specification "
                        "does not exist. \nConsult the managed object "
                        "type reference in the vSphere API documentation."
                        % object_type)

    def __str__(self):
        return self.message
