"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Calendar, CheckCircle, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  useGetGoogleIntegrationStatusApiTenantsTenantIdIntegrationsGoogleStatusGet,
  useListGoogleCalendarsApiTenantsTenantIdIntegrationsGoogleCalendarsGet,
  useDisconnectGoogleCalendarApiTenantsTenantIdIntegrationsGoogleDelete,
  useSetBookingCalendarApiTenantsTenantIdIntegrationsGoogleCalendarPut,
  getGetGoogleIntegrationStatusApiTenantsTenantIdIntegrationsGoogleStatusGetQueryKey,
  getListGoogleCalendarsApiTenantsTenantIdIntegrationsGoogleCalendarsGetQueryKey,
  getGoogleAuthUrlApiTenantsTenantIdIntegrationsGoogleAuthUrlGet
} from "@/lib/api/generated/integrations/integrations";

export default function IntegrationsPage() {
  const params = useParams();
  const tenantId = params.tenantId as string;
  const queryClient = useQueryClient();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { data: statusData, isLoading } = useGetGoogleIntegrationStatusApiTenantsTenantIdIntegrationsGoogleStatusGet(
    tenantId,
    {
      query: {
        enabled: isMounted
      }
    }
  );
  const status = statusData?.data;

  const { data: calendarsData } = useListGoogleCalendarsApiTenantsTenantIdIntegrationsGoogleCalendarsGet(
    tenantId,
    { query: { enabled: isMounted && (status?.connected || false) } }
  );
  const calendars = calendarsData?.data;

  const handleConnect = async () => {
    try {
      const response = await getGoogleAuthUrlApiTenantsTenantIdIntegrationsGoogleAuthUrlGet(tenantId);
      if (response.data.auth_url) {
        window.location.href = response.data.auth_url;
      }
    } catch (e) {
      console.error(e);
    }
  };

  const disconnectMutation = useDisconnectGoogleCalendarApiTenantsTenantIdIntegrationsGoogleDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getGetGoogleIntegrationStatusApiTenantsTenantIdIntegrationsGoogleStatusGetQueryKey(tenantId),
        });
        queryClient.invalidateQueries({
          queryKey: getListGoogleCalendarsApiTenantsTenantIdIntegrationsGoogleCalendarsGetQueryKey(tenantId),
        });
      },
    }
  });

  const setCalendarMutation = useSetBookingCalendarApiTenantsTenantIdIntegrationsGoogleCalendarPut({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getGetGoogleIntegrationStatusApiTenantsTenantIdIntegrationsGoogleStatusGetQueryKey(tenantId),
        });
      },
    }
  });

  if (!isMounted) return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">Loading integrations...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Integrations</h1>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                Google Calendar
              </CardTitle>
              <CardDescription>
                Connect your Google Calendar to enable meeting booking
              </CardDescription>
            </div>
            <div>
              {status?.connected ? (
                <Badge variant="default" className="gap-1">
                  <CheckCircle className="h-3 w-3" />
                  Connected
                </Badge>
              ) : (
                <Badge variant="secondary" className="gap-1">
                  <XCircle className="h-3 w-3" />
                  Not Connected
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {status?.connected ? (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">Select Calendar</label>
                <Select
                  value={status.calendar_id || undefined}
                  onValueChange={(value) => setCalendarMutation.mutate({ tenantId, data: { calendar_id: value } })}
                  disabled={setCalendarMutation.isPending}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a calendar" />
                  </SelectTrigger>
                  <SelectContent>
                    {calendars?.calendars.map((calendar) => (
                      <SelectItem key={calendar.id} value={calendar.id}>
                        {calendar.summary}
                        {calendar.primary && " (Primary)"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {status.calendar_name && (
                  <p className="text-sm text-muted-foreground">
                    Currently using: {status.calendar_name}
                  </p>
                )}
              </div>
              <Button
                variant="destructive"
                onClick={() => disconnectMutation.mutate({ tenantId })}
                disabled={disconnectMutation.isPending}
              >
                {disconnectMutation.isPending ? "Disconnecting..." : "Disconnect"}
              </Button>
            </>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Connect your Google Calendar to allow customers to book meetings directly
                through the chat. The agent will check your availability and create events
                automatically.
              </p>
              <Button
                onClick={handleConnect}
              >
                Connect Google Calendar
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
