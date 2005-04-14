#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005 Shuttleworth Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
RESTive views for access control

$Id$
"""
from zope.app.securitypolicy.interfaces import IPrincipalPermissionManager
from zope.interface import Interface, implements
from schoolbell.app.rest import View, Template
from schoolbell.app.rest.errors import RestError
from schoolbell.app.browser.app import ACLViewBase, hasPermission
from schoolbell.app.rest.xmlparsing import XMLDocument
from schoolbell import SchoolBellMessageID as _
from zope.security.proxy import removeSecurityProxy


class ACLView(View, ACLViewBase):
    """A RESTive view for access control setup"""

    template = Template('www/acl.pt')

    schema = """<?xml version="1.0" encoding="UTF-8"?>
    <grammar xmlns="http://relaxng.org/ns/structure/1.0"
         xmlns:xlink="http://www.w3.org/1999/xlink"
         ns="http://schooltool.org/ns/model/0.1"
         datatypeLibrary="http://www.w3.org/2001/XMLSchema-datatypes">
      <start>
        <element name="acl">
          <zeroOrMore>
            <element name="principal">
              <attribute name="id"><text/></attribute>
              <zeroOrMore>
                <element name="permission">
                  <attribute name="id"><text/></attribute>
                  <optional>
                    <attribute name="setting">
                      <choice>
                        <value>on</value>
                        <value>off</value>
                      </choice>
                    </attribute>
                  </optional>
                </element>
              </zeroOrMore>
            </element>
          </zeroOrMore>
        </element>
      </start>
    </grammar>
    """

    def __init__(self, adapter, request):
        self.context = adapter.context
        self.request = request

    def getPrincipals(self):
        personids = [prin['id'] for prin in self.getPersons()]
        groupids = [prin['id'] for prin in self.getGroups()]
        return groupids + personids

    def POST(self):
        settings = self.parseData(self.request.bodyFile.read())
        manager = IPrincipalPermissionManager(self.context)
        # XXX: alga: the view permission checking does not work!
        # I'll rely on the IPrincipalPermissionManager security for now.
        # # this view is protected by schooltool.controlAccess
        # manager = removeSecurityProxy(manager)
        for principal in settings:
            for permission, title in self.permissions:
                parent = self.context.__parent__
                requested = permission in settings[principal]
                in_parent = hasPermission(permission, parent, principal)
                if requested and not in_parent:
                    manager.grantPermissionToPrincipal(permission, principal)
                elif not requested and in_parent:
                    manager.denyPermissionToPrincipal(permission, principal)
                else:
                    manager.unsetPermissionForPrincipal(permission, principal)

        return _("Permissions updated")

    def parseData(self, body):
        """Extracts the data and validates it.

        Raises a RestError if a principal or permission id is not from
        the allowed set.
        """

        doc = XMLDocument(body, self.schema)
        allowed_principals = self.getPrincipals()
        allowed_permissions = [perm for perm, descritpion in self.permissions]
        try:
            result = {}
            doc.registerNs('m', 'http://schooltool.org/ns/model/0.1')

            for principal in doc.query('/m:acl/m:principal'):
                principalid = principal['id']
                result[principalid] = []
                if principalid not in allowed_principals:
                    raise RestError('Principal "%s" unklown' % principalid)
                for perm in principal.query('m:permission[@setting="on"]'):
                    permission = perm['id']
                    if permission not in allowed_permissions:
                        raise RestError('Permission "%s" not allowed' %
                                        permission)
                    result[principalid].append(permission)

            return result

        finally:
            doc.free()


class IACLAdapter(Interface):
    """A proxy to which the ACL view is hooked up"""


class ACLAdapter:
    """A proxy to which the ACL view is hooked up"""
    implements(IACLAdapter)

    def __init__(self, context):
        self.context = context


class ACLTraverser(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        return ACLAdapter(self.context)
